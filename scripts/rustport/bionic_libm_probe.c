/* G7 leg 1 — the DEVICE's scalar libm, straight from bionic.
 *
 * CPython's math.tanh/math.expm1/math.exp are thin wrappers over the platform
 * libm's double routines (no argument reduction of their own for finite args),
 * so this binary reports exactly the values `math.tanh(x)` would return inside
 * Chaquopy on this device -- without needing a Python on the device at all.
 *
 * Protocol (same wire format as carc-cli): one 16-hex-digit f64 bit pattern per
 * line on stdin, one 16-hex-digit result per line on stdout.
 *
 *   bionic_libm_probe tanh|expm1|exp   < args.hex > out.hex
 *
 * It ALSO compares two such files on the device:
 *
 *   bionic_libm_probe ulp <want.hex> <got.hex>
 *       -> one JSON line: n, n_bit_mismatch, max_ulp, mean_ulp, histogram
 *
 * That mode exists for a boring but decisive reason: the phone is reached over
 * tailscale at ~110 ms RTT and `adb pull` runs at ~140 KB/s, so pulling a 10^7
 * -sample fuzz leg (5 x 34 MB per site per chunk) would have taken hours. The
 * comparison is 40 lines of C, so it runs where the data already is and only the
 * summary crosses the wire. The corpus legs are small enough to pull anyway, and
 * the host cross-checks this code against numpy on them -- so the device-side
 * arithmetic is itself gated rather than trusted.
 *
 * Built with NDK clang for aarch64-linux-android; it links the device's own
 * libm.so at run time, which is the whole point -- do NOT static-link a libm.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <stdint.h>

/* |a - b| in ULPs, via the monotone-int mapping of IEEE-754 -- the same mapping
 * scripts/rustport/harness_transcendental.py::ulp_diff uses, so the numbers this
 * prints are directly comparable with the desktop G0 legs. */
static unsigned long long ulp_gap(uint64_t abits, uint64_t bbits) {
    int64_t ai = (int64_t)abits, bi = (int64_t)bbits;
    if (ai < 0) ai = INT64_MIN - ai;
    if (bi < 0) bi = INT64_MIN - bi;
    return (unsigned long long)(ai > bi ? ai - bi : bi - ai);
}

/* Streaming compare of two hex-bit files. Neither is loaded whole. */
static int cmp_ulp(const char *pa, const char *pb) {
    FILE *fa = fopen(pa, "r"), *fb = fopen(pb, "r");
    if (!fa || !fb) { fprintf(stderr, "cannot open inputs\n"); return 2; }
    char la[64], lb[64];
    unsigned long long n = 0, nmis = 0, maxulp = 0;
    long double sumulp = 0.0L;
    /* Histogram of the mismatching gaps, 1..15 ulp plus an overflow bucket --
     * the shape G0 reports ("<=3 ulp", "<=2 ulp") comes straight out of this. */
    unsigned long long hist[17] = {0};
    /* Both streams are advanced every iteration, independently, so a length
     * difference is caught exactly. Advancing them inside one `&&` would let a
     * one-line difference hide: the short-circuit leaves the other stream
     * unread, and a silent truncation then reads as "no mismatches". */
    int ra = 0;
    for (;;) {
        char *ga = fgets(la, sizeof la, fa);
        char *gb = fgets(lb, sizeof lb, fb);
        if (!ga && !gb) break;
        if (!ga || !gb) { ra = 1; break; }
        uint64_t a = strtoull(la, NULL, 16), b = strtoull(lb, NULL, 16);
        n++;
        if (a == b) continue;
        nmis++;
        unsigned long long d = ulp_gap(a, b);
        if (d > maxulp) maxulp = d;
        sumulp += (long double)d;
        hist[d < 16 ? d : 16]++;
    }
    fclose(fa); fclose(fb);
    printf("{\"n\":%llu,\"n_bit_mismatch\":%llu,\"max_ulp\":%llu,"
           "\"mean_ulp\":%.10g,\"length_mismatch\":%d,\"hist\":{",
           n, nmis, maxulp, n ? (double)(sumulp / n) : 0.0, ra);
    int first = 1;
    for (int i = 1; i <= 16; i++) {
        if (!hist[i]) continue;
        printf("%s\"%d\":%llu", first ? "" : ",", i, hist[i]);
        first = 0;
    }
    printf("}}\n");
    return 0;
}

int main(int argc, char **argv) {
    if (argc < 2) {
        fprintf(stderr, "usage: bionic_libm_probe tanh|expm1|exp|ulp A B|selftest\n");
        return 2;
    }
    if (!strcmp(argv[1], "ulp")) {
        if (argc != 4) { fprintf(stderr, "usage: ... ulp <want> <got>\n"); return 2; }
        return cmp_ulp(argv[2], argv[3]);
    }
    if (!strcmp(argv[1], "selftest")) {
        printf("ok tanh(0)=%.17g expm1(0)=%.17g exp(0)=%.17g\n",
               tanh(0.0), expm1(0.0), exp(0.0));
        return 0;
    }
    int which = !strcmp(argv[1], "tanh") ? 0
              : !strcmp(argv[1], "expm1") ? 1
              : !strcmp(argv[1], "exp") ? 2 : -1;
    if (which < 0) { fprintf(stderr, "unknown fn %s\n", argv[1]); return 2; }

    char line[64];
    while (fgets(line, sizeof line, stdin)) {
        char *p = line;
        while (*p == ' ' || *p == '\t') p++;
        if (*p == '\n' || *p == '\0') continue;
        uint64_t bits = strtoull(p, NULL, 16);
        double x;
        memcpy(&x, &bits, 8);
        double y = which == 0 ? tanh(x) : which == 1 ? expm1(x) : exp(x);
        uint64_t out;
        memcpy(&out, &y, 8);
        printf("%016llx\n", (unsigned long long)out);
    }
    return 0;
}
