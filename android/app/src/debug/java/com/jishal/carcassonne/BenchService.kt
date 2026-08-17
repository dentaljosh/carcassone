package com.jishal.carcassonne

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Intent
import android.content.pm.ApplicationInfo
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.IBinder
import android.os.PowerManager
import android.util.Log
import com.chaquo.python.Python
import java.io.File

/**
 * DEBUG-ONLY battery-bench workload runner. This class lives in the `debug`
 * sourceset, so release APKs do not contain it (that, not a runtime flag, is
 * the primary guard; the DEBUGGABLE check below is belt-and-braces).
 *
 * Started headlessly from the host driver (`android/tools/battery_bench.sh`):
 *
 *   adb shell am start-foreground-service \
 *     -n com.jishal.carcassonne/.BenchService \
 *     --ei n_moves 24 --ei rust_threads 4 --ei seed 424242 --es tag t4_r1
 *
 * It renders nothing: a foreground-service notification plus a partial
 * wakelock keep the CPU running with the screen off, which is exactly the
 * measurement condition the driver wants. All real work happens in
 * `carc_bench.run_bench` (debug-sourceset Python), which writes
 * `files/bench/<tag>.json` — never the E4 archive dir `files/games/`.
 *
 * The Python call runs on a dedicated thread, NOT on [PythonBridge]'s bridge
 * thread: the bench must not queue behind (or in front of) a live game's
 * `ai_move`. The runbook says to run with no game in progress anyway.
 */
class BenchService : Service() {

    private var wakeLock: PowerManager.WakeLock? = null

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if ((applicationInfo.flags and ApplicationInfo.FLAG_DEBUGGABLE) == 0) {
            Log.e(TAG, "refusing to run in a non-debuggable build")
            stopSelf()
            return START_NOT_STICKY
        }
        if (running) {
            Log.w(TAG, "bench already running; ignoring new start request")
            return START_NOT_STICKY
        }
        val nMoves = intent?.getIntExtra("n_moves", 24) ?: 24
        val threads = intent?.getIntExtra("rust_threads", -1) ?: -1
        val seed = intent?.getIntExtra("seed", 424242) ?: 424242
        val tag = intent?.getStringExtra("tag") ?: "bench_${threads}t_${System.currentTimeMillis()}"
        // TIE ARBITER arm (tiearb2 Stage 2). 0 (the default) == the champion as
        // deployed: `carc_bench` passes NO arbiter keyword to the rust config at
        // all. mode/salt/eps are omitted here on purpose so the arm defaults to
        // the settings of record spelled once, in `carc_bench`.
        val tiearbB = intent?.getIntExtra("tiearb_b", 0) ?: 0
        val tiearbJ = intent?.getIntExtra("tiearb_j", 4) ?: 4
        val tiearbMode = intent?.getStringExtra("tiearb_mode")
        val tiearbSalt = intent?.getStringExtra("tiearb_salt")
        if (threads < 1) {
            Log.e(TAG, "missing/bad --ei rust_threads (got $threads); not starting")
            stopSelf()
            return START_NOT_STICKY
        }

        startInForeground()
        running = true
        wakeLock = (getSystemService(POWER_SERVICE) as PowerManager)
            .newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "carc:bench")
            .apply { acquire(WAKELOCK_TIMEOUT_MS) }

        Log.i(TAG, "START tag=$tag n_moves=$nMoves rust_threads=$threads seed=$seed " +
            "tiearb_b=$tiearbB tiearb_j=$tiearbJ")
        Thread({
            try {
                // CarcApplication.onCreate already started Chaquopy.
                val py = Python.getInstance()
                val outDir = File(filesDir, BENCH_DIR).absolutePath
                // Positional through `k_dets` (null/null = the YAML champion
                // budget, as the on-device service always benches), then the
                // arbiter arm. Chaquopy maps Kotlin null -> Python None.
                val result = py.getModule("carc_bench")
                    .callAttr(
                        "run_bench", nMoves, threads, seed, outDir, tag,
                        null, null, tiearbB, tiearbJ, tiearbMode, tiearbSalt,
                    )
                    .toString()
                // One parseable completion line; the driver polls for the file,
                // logcat is the human-readable trail.
                val ok = result.contains("\"ok\": true")
                Log.i(TAG, "DONE tag=$tag ok=$ok file=$outDir/$tag.json")
                if (!ok) Log.e(TAG, "bench result: $result")
            } catch (t: Throwable) {
                Log.e(TAG, "bench crashed (tag=$tag)", t)
            } finally {
                wakeLock?.let { if (it.isHeld) it.release() }
                wakeLock = null
                running = false
                stopSelf()
            }
        }, "carc-bench").start()
        return START_NOT_STICKY
    }

    private fun startInForeground() {
        val nm = getSystemService(NOTIFICATION_SERVICE) as NotificationManager
        nm.createNotificationChannel(
            NotificationChannel(
                CHANNEL_ID, "Battery bench (debug)",
                NotificationManager.IMPORTANCE_LOW,
            )
        )
        val notification = Notification.Builder(this, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.stat_notify_sync)
            .setContentTitle("Carcassonne battery bench")
            .setContentText("Running champion moves headlessly (debug build)")
            .build()
        if (Build.VERSION.SDK_INT >= 34) {
            startForeground(
                NOTIF_ID, notification,
                ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC,
            )
        } else {
            startForeground(NOTIF_ID, notification)
        }
    }

    companion object {
        const val TAG = "CarcBench"
        private const val CHANNEL_ID = "carc_bench"
        private const val NOTIF_ID = 4242
        private const val BENCH_DIR = "bench"

        // Generous ceiling: worst arm is rust_threads=1 at the full champion
        // budget; the driver's own per-run timeout is much tighter.
        private const val WAKELOCK_TIMEOUT_MS = 30L * 60L * 1000L

        @Volatile
        private var running = false
    }
}
