/* Fixed adversarial feasibility probe. Not a worker entry point.
 * Built only by an explicitly authorized operator probe; never run on host.
 * Exit nonzero unless every negative check and positive control succeeds.
 */
#define _GNU_SOURCE
#include <arpa/inet.h>
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <unistd.h>

extern char **environ;
static int failures;
static void check(int ok) { if (!ok) failures++; }
static void absent(const char *path) {
    int fd = open(path, O_RDONLY | O_NONBLOCK);
    check(fd < 0 && (errno == ENOENT || errno == EACCES));
    if (fd >= 0) close(fd);
    fd = open(path, O_WRONLY | O_CREAT | O_NONBLOCK, 0600);
    check(fd < 0);
    if (fd >= 0) close(fd);
}
int main(int argc, char **argv) {
    if (argc != 5) return 2;
    /* Refuse to attempt any adversarial I/O if namespace setup was ineffective.
       In particular, a refused external port on the host proves nothing. */
    const char *namespaces[] = {"/proc/self/ns/net", "/proc/self/ns/pid", "/proc/self/ns/mnt"};
    for (unsigned i = 0; i < 3; i++) {
        char current[128] = {0};
        ssize_t n = readlink(namespaces[i], current, sizeof(current)-1);
        if (n <= 0 || strcmp(current, argv[i + 2]) == 0) return 1;
    }
    check(environ[0] == NULL);
    check(getuid() == 65534 && getgid() == 65534);
    for (int fd = 3; fd < 64; fd++) {
        errno = 0;
        check(fcntl(fd, F_GETFD) == -1 && errno == EBADF);
    }
    const char *paths[] = {"/home/credential", "/root/credential", "/repo/evaluator",
        "/evaluator", "/state.json", "/events.jsonl", "/mnt/credential",
        "/proc/1/root/state.json", "/proc/self/root/state.json", argv[1]};
    for (unsigned i = 0; i < sizeof(paths)/sizeof(paths[0]); i++) absent(paths[i]);
    check(symlink(argv[1], "/tmp/escape") == 0);
    absent("/tmp/escape");
    int fd = open("/tmp/control", O_CREAT | O_RDWR | O_EXCL, 0600);
    check(fd >= 0);
    if (fd >= 0) { check(write(fd, "ok", 2) == 2); close(fd); }
    DIR *proc = opendir("/proc");
    check(proc != NULL);
    if (proc) {
        struct dirent *entry;
        while ((entry = readdir(proc))) {
            char *end;
            long pid = strtol(entry->d_name, &end, 10);
            if (!*end && pid > 0) check(pid == 1 || pid == getpid());
        }
        closedir(proc);
    }
    /* Only loopback may exist, and it must be down in this fresh namespace. */
    FILE *dev = fopen("/proc/net/dev", "r");
    check(dev != NULL);
    if (dev) {
        char line[512];
        while (fgets(line, sizeof(line), dev)) {
            char *colon = strchr(line, ':');
            if (colon) {
                *colon = 0;
                char *name = line;
                while (*name == ' ') name++;
                check(strcmp(name, "lo") == 0);
            }
        }
        fclose(dev);
    }
    const char *addresses[] = {"127.0.0.1", "198.51.100.1"};
    for (unsigned i = 0; i < 2; i++) {
        fd = socket(AF_INET, SOCK_STREAM | SOCK_NONBLOCK, 0);
        check(fd >= 0);
        if (fd >= 0) {
            struct sockaddr_in addr = {.sin_family = AF_INET, .sin_port = htons(9)};
            inet_pton(AF_INET, addresses[i], &addr.sin_addr);
            int rc = connect(fd, (struct sockaddr *)&addr, sizeof(addr));
            check(rc == -1 && errno == ENETUNREACH);
            close(fd);
        }
    }
    if (failures) return 1;
    puts("{\"filesystem\":true,\"environment\":true,\"fds\":true,\"process\":true,\"network\":true,\"control\":true}");
    return 0;
}
