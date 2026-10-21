#!/usr/bin/env python3
"""Run one command and record wall time, CPU time and process-tree memory.

Memory is sampled every second over every process in the command's session:
  peak_pss_gb  sum of PSS (shared pages split between sharers; right for forked R/Python workers)
  peak_rss_gb  sum of RSS (double-counts shared pages; upper bound)
CPU time: rusage of reaped descendants, and separately the sum over every sampled process of its last seen
/proc/<pid>/stat utime+stime (catches forked workers that rusage misses, e.g. R mclapply; misses processes
that live < 1 s). The larger of the two is reported as cpu_total_s.

usage: measure.py <out.json> -- <command> [args...]
"""
import json, os, resource, subprocess, sys, threading, time


CLK = os.sysconf("SC_CLK_TCK")


def cpu_s(pid):
    try:
        with open(f"/proc/{pid}/stat") as f:
            fields = f.read().rsplit(")", 1)[1].split()
        return (int(fields[11]) + int(fields[12])) / CLK  # utime, stime
    except (OSError, IndexError, ValueError):
        return None


def session_pids(sid):
    pids = []
    for p in os.listdir("/proc"):
        if not p.isdigit():
            continue
        try:
            with open(f"/proc/{p}/stat") as f:
                fields = f.read().rsplit(")", 1)[1].split()
            if int(fields[3]) == sid:  # field 6 (session) after the ")" split
                pids.append(int(p))
        except (OSError, IndexError, ValueError):
            pass
    return pids


ROLLUP = os.path.exists("/proc/self/smaps_rollup")


def mem_kb(pid):
    """(PSS, RSS) in kB; smaps_rollup when the kernel has it (>= 4.14), else sum the per-mapping smaps lines."""
    pss = rss = 0
    try:
        with open(f"/proc/{pid}/smaps_rollup" if ROLLUP else f"/proc/{pid}/smaps") as f:
            for line in f:
                if line.startswith("Pss:"):
                    pss += int(line.split()[1])
                elif line.startswith("Rss:"):
                    rss += int(line.split()[1])
    except OSError:
        pass
    return pss, rss


def main():
    out = sys.argv[1]
    cmd = sys.argv[sys.argv.index("--") + 1:]
    t0 = time.time()
    proc = subprocess.Popen(cmd, start_new_session=True)
    peak = {"pss": 0, "rss": 0, "nproc": 0}
    samples = []
    cpu_seen = {}  # pid -> last cumulative cpu seconds
    stop = threading.Event()

    def sampler():
        while not stop.is_set():
            pids = session_pids(proc.pid)
            pss = rss = 0
            for p in pids:
                a, b = mem_kb(p)
                pss += a; rss += b
                c = cpu_s(p)
                if c is not None:
                    cpu_seen[p] = max(cpu_seen.get(p, 0.0), c)
            peak["pss"] = max(peak["pss"], pss)
            peak["rss"] = max(peak["rss"], rss)
            peak["nproc"] = max(peak["nproc"], len(pids))
            samples.append((round(time.time() - t0, 1), pss, rss, len(pids)))
            stop.wait(1.0)

    th = threading.Thread(target=sampler, daemon=True)
    th.start()
    rc = proc.wait()
    wall = time.time() - t0
    stop.set(); th.join()
    ru = resource.getrusage(resource.RUSAGE_CHILDREN)
    ru_cpu = ru.ru_utime + ru.ru_stime
    sampled_cpu = sum(cpu_seen.values())
    cpu = max(ru_cpu, sampled_cpu)
    rec = {
        "command": cmd,
        "exit_code": rc,
        "wall_s": round(wall, 2),
        "cpu_user_s": round(ru.ru_utime, 2),
        "cpu_sys_s": round(ru.ru_stime, 2),
        "cpu_rusage_s": round(ru_cpu, 2),
        "cpu_sampled_s": round(sampled_cpu, 2),
        "cpu_total_s": round(cpu, 2),
        "avg_cores_busy": round(cpu / wall, 2) if wall else None,
        "peak_pss_gb": round(peak["pss"] / 1048576, 3),
        "peak_rss_sum_gb": round(peak["rss"] / 1048576, 3),
        "max_single_rss_gb_rusage": round(ru.ru_maxrss / 1048576, 3),
        "peak_nproc": peak["nproc"],
        "host": os.uname().nodename,
        "start_epoch": t0,
    }
    with open(out, "w") as f:
        json.dump(rec, f, indent=1)
    with open(out.replace(".json", "") + ".mem.tsv", "w") as f:
        f.write("t_s\tpss_kb\trss_kb\tnproc\n")
        for s in samples:
            f.write("\t".join(map(str, s)) + "\n")
    print(json.dumps(rec))
    sys.exit(rc)


if __name__ == "__main__":
    main()
