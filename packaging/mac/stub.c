/* Main executable of "Apofiz Play GTA6.app".
 *
 * Embeds the bundled CPython (Contents/Resources/python) and runs
 * `python -m launcher` from Contents/Resources/app. Embedding (instead of
 * exec'ing python3) keeps the process inside the bundle, so macOS uses our
 * Info.plist (LSUIElement, icon, NSLocalNetworkUsageDescription) and shows
 * "Apofiz Play GTA6" in permission prompts.
 *
 * Children (server.py, agent.py) are started with APOFIZ_PYTHON, the real
 * bundled interpreter.
 */
#include <libgen.h>
#include <limits.h>
#include <mach-o/dyld.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <Python.h>

int main(int argc, char **argv) {
    char exe[PATH_MAX], real[PATH_MAX], contents[PATH_MAX], buf[PATH_MAX];
    uint32_t size = sizeof(exe);
    if (_NSGetExecutablePath(exe, &size) != 0 || !realpath(exe, real)) {
        fprintf(stderr, "ApofizPlay: cannot resolve executable path\n");
        return 1;
    }
    /* real = .../Contents/MacOS/ApofizPlay -> contents = .../Contents */
    strlcpy(buf, real, sizeof(buf));
    strlcpy(contents, dirname(dirname(buf)), sizeof(contents));

    char home[PATH_MAX], app[PATH_MAX], py[PATH_MAX];
    snprintf(home, sizeof(home), "%s/Resources/python", contents);
    snprintf(app, sizeof(app), "%s/Resources/app", contents);
    snprintf(py, sizeof(py), "%s/bin/python3", home);

    setenv("PYTHONHOME", home, 1);
    setenv("PYTHONNOUSERSITE", "1", 1);
    setenv("PYTHONDONTWRITEBYTECODE", "1", 1);  /* never modify the signed bundle */
    setenv("APOFIZ_BUNDLED", "1", 1);
    setenv("APOFIZ_APP_ROOT", app, 1);
    setenv("APOFIZ_PYTHON", py, 1);
    unsetenv("PYTHONPATH");
    unsetenv("PYTHONSTARTUP");
    if (chdir(app) != 0) {
        perror("ApofizPlay: chdir");
        return 1;
    }

    /* argv for Python: <exe> -s -m launcher [user args] */
    char **pargv = calloc((size_t)argc + 4, sizeof(char *));
    int n = 0;
    pargv[n++] = argv[0];
    pargv[n++] = "-s";
    pargv[n++] = "-m";
    pargv[n++] = "launcher";
    for (int i = 1; i < argc; i++) {
        if (strncmp(argv[i], "-psn_", 5) == 0) continue;  /* Finder process serial number */
        pargv[n++] = argv[i];
    }
    pargv[n] = NULL;
    return Py_BytesMain(n, pargv);
}
