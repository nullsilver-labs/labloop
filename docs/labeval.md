# Hiding the labels: the `labeval` user

`lab eval` is the only reader of the search and final labels. Without privilege
separation that is a convention: the worker runs as you, so it *could* read
`$LAB_PRIVATE`. REPORT.md says "privilege separation for labels | OFF" in that case.

To make it mechanical on a single Ubuntu box (one-time, needs sudo):

```sh
sudo adduser --system --group --no-create-home labeval
sudo mkdir -p /srv/labloop-private && sudo chown labeval:labeval /srv/labloop-private
sudo chmod 700 /srv/labloop-private
# let your user run exactly one thing as labeval, without a password:
echo "$USER ALL=(labeval) NOPASSWD: /usr/bin/python3" | sudo tee /etc/sudoers.d/labloop-eval
sudo chmod 440 /etc/sudoers.d/labloop-eval
```

Then put the labels under `/srv/labloop-private/<campaign-id>/{search,final}/` owned by
`labeval` (mode 700), set in `campaign.toml`:

```toml
[eval]
user = "labeval"
[data.search]
labels = "/srv/labloop-private/<campaign-id>/search"
[data.final]
labels = "/srv/labloop-private/<campaign-id>/final"
```

and leave `LAB_PRIVATE` unset in the environment that runs `lab run` (the worker
never receives it either way). `lab eval` then runs
`sudo -n -u labeval python3 <evaluator> <predictions> <labels>`; the worker process,
running as you, gets `EACCES` on the labels directory.

The evaluator script must be readable by `labeval` and must not import from the
candidate's code. The sudoers line grants `python3` in general, so keep the evaluator
short and reviewable; a tighter line names the exact script path instead.

The acceptance suite does not require this setup. It asserts what can be asserted
without root: the worker's environment carries no `LAB_PRIVATE`, the guard hook blocks
a worker command that names the labels, and fitness is written only by `lab`.
