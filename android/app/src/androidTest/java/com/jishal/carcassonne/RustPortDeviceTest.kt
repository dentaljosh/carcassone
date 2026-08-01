package com.jishal.carcassonne

import android.util.Log
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.chaquo.python.PyObject
import com.chaquo.python.Python
import org.json.JSONObject
import org.junit.Assert.assertTrue
import org.junit.BeforeClass
import org.junit.FixMethodOrder
import org.junit.Test
import org.junit.runner.RunWith
import org.junit.runners.MethodSorters
import java.io.File

/**
 * G7 — the on-device half of the Rust-port gate (P7).
 *
 * WHY AN INSTRUMENTED TEST AND NOT A SHELL SCRIPT
 * -----------------------------------------------
 * Three of the four device legs need things that exist only INSIDE the app
 * process: the Chaquopy interpreter, the `numpy` Chaquopy installed for this ABI,
 * and the `carc_rs` wheel as pip actually resolved it. None of that is reachable
 * from `adb shell` — Chaquopy's CPython is a library loaded by the JVM, not an
 * executable. An instrumented test is the only surface that runs arbitrary code
 * in that environment WITHOUT adding a debug hook to the shipping app, which is
 * why this is a test and not a new bridge entry point.
 *
 * The fourth leg (bionic's scalar libm) does NOT need this and deliberately does
 * not live here — `scripts/rustport/device_libm_probe.py` drives NDK-built
 * binaries over adb for that, because `math.tanh` is a thin wrapper over libm and
 * a native probe is a more direct measurement than a Python one.
 *
 * OUTPUT
 * ------
 * Every leg writes a JSON file to the app's external files dir. Collect with:
 *
 *   adb shell run-as com.jishal.carcassonne ls files/p7        # or:
 *   adb pull /sdcard/Android/data/com.jishal.carcassonne/files/p7 measurement/rustport_p7/device
 *
 * The tests assert only on things that would make a number MEANINGLESS (a missing
 * wheel, a divergent replay). Latency bars are reported, not asserted: a thermal
 * result that fails its bar is a finding for the gate write-up, and a red test
 * that stops the remaining legs from running would cost more than it buys.
 */
@RunWith(AndroidJUnit4::class)
@FixMethodOrder(MethodSorters.NAME_ASCENDING)
class RustPortDeviceTest {

    // ---------------------------------------------------------------- setup --
    private fun probe(): PyObject = Python.getInstance().getModule(MODULE)

    private fun emit(name: String, json: String) {
        val dir = File(appCtx().getExternalFilesDir(null), "p7").apply { mkdirs() }
        File(dir, "$name.json").writeText(json)
        // Also to logcat, so a leg's answer survives even if the pull fails.
        Log.i(TAG, "$name = ${json.take(4000)}")
    }

    // ----------------------------------------------------------------- legs --

    /** Leg 0: what actually loaded. Read this first when anything looks odd. */
    @Test
    fun t00_environment() {
        val json = probe().callAttr("environment_report").toString()
        emit("environment", json)
        val o = JSONObject(json)
        assertTrue(
            "carc_rs did not import on device: ${o.getJSONObject("carc_rs")}",
            o.getJSONObject("carc_rs").getBoolean("ok"),
        )
        assertTrue(
            "numpy did not import on device",
            o.getJSONObject("numpy").getBoolean("ok"),
        )
    }

    /**
     * Leg 1b: the DEVICE's numpy `np.exp` and `math.tanh`/`math.expm1` against
     * every `compat::LibmFlavor`. This is the half of G7 leg 1 that the native
     * probe cannot answer, because `np.exp` on a float64 ndarray is numpy's own
     * SIMD kernel rather than libm's `exp`.
     *
     * NOT asserted: parity. The build spec pre-registers a fallback for exactly
     * this outcome, and the G0 fleet amendment (Apple's libm was a THIRD
     * implementation) is why the answer has to be measured rather than assumed.
     * A red test here would be a wrong claim about what the gate is.
     */
    @Test
    fun t10_libmFlavor() {
        val npz = asset("p7/transcendental_inputs.npz")
        val json = probe().callAttr(
            "libm_report", npz.absolutePath, FUZZ_N, 20260731,
        ).toString()
        emit("libm_chaquopy", json)
        val v = JSONObject(json).getJSONObject("verdict")
        Log.w(TAG, "LIBM VERDICT parity=${v.getBoolean("platform_parity_achieved")} $v")
    }

    /**
     * Leg 2: replay identity vs desktop — both E4 phone archives plus 20 champ
     * games, per-ply byte-equal `string_representation` and scores, compared
     * against digests frozen on the desktop by
     * `scripts/rustport/p7_make_device_assets.py`.
     *
     * This one IS asserted: it is a bit-exactness claim, and the spec's bar for
     * those is "0 mismatches, full stop".
     */
    @Test
    fun t20_replayIdentity() {
        val expect = asset("p7/replay_expect.json")
        val json = probe().callAttr("replay_report", expect.absolutePath).toString()
        emit("replay", json)
        val o = JSONObject(json)
        assertTrue(
            "on-device replay diverged from desktop: $json",
            o.getBoolean("all_identical"),
        )
    }

    /** Leg 3a: the full champion budget, k8x1376. Gate bar: median <= 2 s/move. */
    @Test
    fun t30_benchFullBudget() = bench("bench_k8x1376", sims = 1376, kDets = 8)

    /**
     * Leg 3b: the CURRENT on-device carve-out, k4x688 — the cell the 1.7 s/move
     * Python baseline was measured at, so this is the like-for-like comparison.
     */
    @Test
    fun t31_benchMobileBudget() = bench("bench_k4x688", sims = 688, kDets = 4)

    /** Leg 4: 50-move thermal soak at the full budget, with the throttle curve. */
    @Test
    fun t40_thermalSoak() {
        val json = probe().callAttr(
            "soak_report",
            *kwargs(
                mapOf(
                    "knobs_path" to asset("p7/knobs.json").absolutePath,
                    "battery_path" to asset("p7/battery.json").absolutePath,
                    "sims" to 1376, "k_dets" to 8, "threads" to THREADS,
                    "exp_fma" to true, "tanh_flavor" to TANH_FLAVOR,
                    "moves" to 50,
                ),
            ),
        ).toString()
        emit("soak_k8x1376", json)
        val o = JSONObject(json)
        Log.w(TAG, "SOAK throttle_ratio=${o.opt("throttle_ratio")} " +
            "first10=${o.opt("first10_mean_s")} last10=${o.opt("last10_mean_s")}")
    }

    // ------------------------------------------------------------- plumbing --

    private fun bench(name: String, sims: Int, kDets: Int) {
        val json = probe().callAttr(
            "bench_report",
            *kwargs(
                mapOf(
                    "knobs_path" to asset("p7/knobs.json").absolutePath,
                    "battery_path" to asset("p7/battery.json").absolutePath,
                    "sims" to sims, "k_dets" to kDets, "threads" to THREADS,
                    "exp_fma" to true, "tanh_flavor" to TANH_FLAVOR,
                ),
            ),
        ).toString()
        emit(name, json)
        val med = JSONObject(json).getJSONObject("s_per_move").getDouble("median")
        Log.w(TAG, "$name median=${med}s (bar 2.0s)")
    }

    companion object {
        private const val TAG = "P7Device"
        private const val MODULE = "carc_p7_probe"

        /**
         * Worker threads for the k-parallel PIMC split. The phone's big+mid core
         * count; the soak is what says whether it is the right number under heat.
         */
        private const val THREADS = 4

        /**
         * ⚠️ Set from G7 leg 1's ANSWER, not from the desktop's. The desktop is
         * `glibc_fma` (G0 §2); bionic is a different libm, and the whole point of
         * leg 1 was to find out which.
         *
         * MEASURED 2026-08-01 on this Pixel 9 Pro (measurement/rustport_p7/
         * G7_libm_device.json): bionic `tanh` and `expm1` are **`msun`**, exact on
         * the 214,333-arg production corpus AND on 10^7 fuzz args. `glibc` also
         * passed the tanh CORPUS (0/214,333) and then failed the fuzz
         * (12,867/10^7) — G0's cautionary tale reproduced on a second platform, so
         * do not re-derive this flavour from a corpus-only run.
         */
        private const val TANH_FLAVOR = "msun"

        /** Fuzz samples per implementation on-device. Desktop G0 used 1e8. */
        private const val FUZZ_N = 2_000_000

        private fun appCtx() =
            InstrumentationRegistry.getInstrumentation().targetContext

        /**
         * Chaquopy reads a `Kwarg` in the varargs list as a keyword argument, so
         * every one of these probe entry points is called by NAME. That is
         * deliberate: `bench_report` takes seven parameters whose positional
         * order nothing else enforces, and a silently transposed
         * `sims`/`k_dets` would produce a plausible-looking wrong number.
         */
        private fun kwargs(m: Map<String, Any?>): Array<Any?> =
            m.map { (k, v) -> com.chaquo.python.Kwarg(k, v) as Any? }.toTypedArray()

        /**
         * Copy an asset out of the TEST apk into the app's cache dir.
         *
         * It has to become a real file: `np.load` and `Path.read_text` take paths,
         * and an APK asset is a zip entry with no filesystem identity. The test
         * apk's assets live on the INSTRUMENTATION context, not the target one.
         */
        private fun asset(path: String): File {
            val out = File(appCtx().cacheDir, "p7assets/$path")
            if (out.isFile && out.length() > 0) return out
            out.parentFile?.mkdirs()
            InstrumentationRegistry.getInstrumentation().context.assets.open(path)
                .use { input -> out.outputStream().use { input.copyTo(it) } }
            return out
        }

        @BeforeClass
        @JvmStatic
        fun startPython() {
            // CarcApplication normally does this; an instrumented run may reach the
            // test before any Activity has forced it, so make it explicit.
            if (!Python.isStarted()) {
                Python.start(
                    com.chaquo.python.android.AndroidPlatform(appCtx()),
                )
            }
        }
    }
}
