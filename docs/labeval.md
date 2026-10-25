# Hiding the labels: the `labeval` user

`lab eval` is the only reader of the search and final labels. Without privilege
separation that is a convention: the worker runs as you, so it *could* read
`$LAB_PRIVATE`. REPORT.md says "privilege separation for labels | OFF" in that case.

With an eval user the labels belong to `labeval`, mode 700, and `lab eval` reaches them
through one sudoers line. Everything rests on that line: whatever it lets *you* run as
`labeval`, a worker can run too, because the worker is you. Its `code/run.sh` runs as
you, outside any hook, so the guard's refusal of `sudo` in a worker's commands is a
tripwire, not the wall. The wall is that the sudoers line names one root-owned program.

## What went wrong before (October 2026)

Earlier versions of this page recommended

```
<you> ALL=(labeval) NOPASSWD: /usr/bin/python3
```

That grants `python3` as `labeval` with any arguments, so
`sudo -n -u labeval python3 -c 'print(open("/srv/labloop-private/…").read())'` printed the
labels to any process of yours. The evaluator was also yours to edit, and its sha256
was recorded but never checked. Campaigns run that way were hidden from a worker that
followed its job card, not from one that went looking. See NEXT.md.

## The setup

One-time per campaign, as root, with the script that does exactly this
([scripts/labeval-install.sh](../scripts/labeval-install.sh)). Read it first; lab and
agents never run it.

```sh
sudo bash scripts/labeval-install.sh <campaign-id> eval/score.py [eval/helper.py …] \
     --labels /path/to/staged/labels [--drop-general-line]
```

It leaves:

| path | owner, mode | what |
|---|---|---|
| `/opt/labloop-eval/<id>/score.py` (+ helpers) | root, 644 | a copy of the evaluator, in a dir only root can write |
| `/opt/labloop-eval/<id>/evaluate` | root, 755 | `exec /usr/bin/python3 -E -s …/score.py "$@"`: the one path sudo may run |
| `/etc/sudoers.d/labloop-eval-<id>` | root, 440 | `<you> ALL=(labeval) NOPASSWD: /opt/labloop-eval/<id>/evaluate` (checked with `visudo -c`) |
| `/srv/labloop-private/<id>/{search,final}` | labeval, 700 | the labels |

`--drop-general-line` moves the old `/etc/sudoers.d/labloop-eval` (the `python3` line)
to `/root/labloop-eval-backup/`. Leave it off while a campaign that still uses that
line is running: its evaluations would start failing. Without it the script prints a
warning that the general line still gives the labels away.

Then in `campaign.toml`:

```toml
[data]
evaluator = "/opt/labloop-eval/<campaign-id>/evaluate"
[data.search]
labels = "/srv/labloop-private/<campaign-id>/search"
[data.final]
labels = "/srv/labloop-private/<campaign-id>/final"
[eval]
user = "labeval"
```

and leave `LAB_PRIVATE` unset in the environment that runs `lab run` (the worker never
receives it either way). `lab eval` then runs
`sudo -n -u labeval /opt/labloop-eval/<id>/evaluate <predictions> <labels>`; a worker
process gets `EACCES` on the labels and `sudo` refuses it anything else as `labeval`.

What lab checks on its side:

- **The evaluator is frozen.** Its sha256 goes into `population.json` when the campaign
  starts, and every evaluation re-hashes it first. A different evaluator stops the loop
  as a tooling error; the candidate stays unsettled until the frozen one is back.
  REPORT.md prints the hash.
- **Custody.** `lab campaign check` warns when an eval user is set but the evaluator, or
  a dir above it, is not root-owned and root-writable only; REPORT.md says so next to
  "privilege separation". The hash catches a change after the start; custody says
  whether a worker could have made one.
- **Scores come only from lab.** A `fitness.json` lab did not write (none exists before
  the first evaluation; a worker's `run.sh` writing `../fitness.json`, or a child that
  copied its parent's dir) is renamed `fitness.worker.json` at settlement and the
  candidate is invalid. A frozen candidate whose final run changes `fitness.json` gets
  its file quarantined the same way, lab's search record back, and no final read.

## Evaluators that run docker

An evaluator that runs the candidate's code in a container (labloop-compress) used to
put `labeval` in the `docker` group. The docker group is root on the box: whoever is in
it can mount `/srv/labloop-private` into a container. Instead:

```sh
sudo bash scripts/labeval-install.sh <campaign-id> eval/score.py eval/measure.py \
     --docker <image>@sha256:<digest> --labels …
```

removes `labeval` from the docker group and installs `/opt/labloop-eval/<id>/sandbox`,
root-owned, which `labeval` (and nobody else) may run as root:

```
sandbox <workdir> <argv…>
```

It runs `argv` in the pinned image with `--network none`, no capabilities, as labeval's
uid, with `<workdir>` mounted at `/work` and nothing else. `<workdir>` must be a dir
`labeval` owns under `/var/lib/labloop-eval/<id>/work/`. The evaluator copies the
candidate's code and the hidden input there, then calls
`sudo -n /opt/labloop-eval/<id>/sandbox <workdir> ./compress …` where it used to call
`docker run`. The image is pinned by digest so a retag cannot swap it.

## What this does not cover

- **You in `docker` or `lxd`.** Membership in either reads every file on the box, so a
  worker running as you can mount the labels without any sudo. The script warns about
  it. Hidden-by-the-OS needs the account that runs workers out of both groups (rootless
  docker for your own use), or workers under an account of their own.
- **The evaluator as an oracle.** A worker can still run the evaluator as `labeval`
  through the sudoers line: it cannot read the labels, but it can score predictions of
  its own on the search split, or the final one, as often as it likes. Only running
  workers under another account closes that.
- **A cached sudo password.** sudo's credential cache is per terminal (Ubuntu's default
  `timestamp_type=tty`); a worker has no terminal, so a password you typed elsewhere does
  not carry over to it. Keep it that way.

The acceptance suite does not need root. It asserts what can be asserted without it:
the worker's environment carries no `LAB_PRIVATE`; the guard blocks a worker command
that names the labels or runs `sudo`; fitness is written only by `lab`; a worker's
`fitness.json` is quarantined; a changed evaluator is refused.
