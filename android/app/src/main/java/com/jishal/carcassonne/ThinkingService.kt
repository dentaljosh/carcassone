package com.jishal.carcassonne

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.IBinder
import android.os.PowerManager
import android.util.Log

/**
 * Keeps the opponent's turn running while the app is not the foreground app.
 *
 * ## What problem this actually solves
 *
 * Backgrounding the app does not stop the search — the bridge thread is an
 * ordinary daemon thread and the process is still alive. What it does is move the
 * process out of the **top-app cpuset** and make it a candidate for being killed
 * under memory pressure. On the Pixel that means a champion move that takes ~3 s
 * with the app on screen can take many times that with it in the background,
 * because the process is confined to the little cores. A foreground service with a
 * visible notification is the supported way to say "this process is doing work the
 * user asked for" and keep the scheduling class.
 *
 * The same service covers BOTH opponents, for two different reasons:
 *  - the **local champion**, because the search runs here and needs the CPU;
 *  - the **remote Carcasum**, because the server computes regardless but the phone
 *    still has to hold an open HTTP request for the whole think, and a backgrounded
 *    process with a dropped socket costs a retry (or, if the process dies, a
 *    re-request on resume).
 *
 * ## Why it is only a scheduling aid, never the correctness story
 *
 * A move is NEVER lost by the process dying mid-search, with or without this
 * service. `GameViewModel` writes the autosave *before* every `ai_move`, so a
 * killed process resumes from the human position that preceded the search and the
 * opponent thinks again — deterministically, because the champion's per-move seeds
 * are re-seated from the replayed `_move_idx`, and because the remote server
 * answers an identical `(deck_seed, actions)` request from its committed log rather
 * than searching twice. This service makes that path rare; it is not what makes it
 * safe. See `android_bridge.restore_game`.
 *
 * ## The Android 14+ contract
 *
 * `foregroundServiceType="dataSync"` (declared in the manifest, matched by the
 * `ServiceInfo` constant below on API 34+) plus `FOREGROUND_SERVICE_DATA_SYNC`.
 * The type is the same one `BenchService` uses in the debug sourceset, and is
 * chosen over `shortService` deliberately: `shortService` caps at ~3 minutes and
 * cannot be extended, which a long endgame solve on a cold device could exceed.
 * `POST_NOTIFICATIONS` is requested at runtime on API 33+; a DENIED permission
 * hides the notification but does not stop the service, so nothing here is gated
 * on it.
 *
 * Started only from the foreground (the human has just moved, so the app is on
 * screen), which is what makes the start legal under the Android 12+ background
 * FGS-start restrictions. Every start/stop is wrapped: a refusal degrades to the
 * old behaviour — the turn still runs, just without the scheduling guarantee.
 */
class ThinkingService : Service() {

    private var wakeLock: PowerManager.WakeLock? = null

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val who = intent?.getStringExtra(EXTRA_OPPONENT).orEmpty().ifEmpty { DEFAULT_WHO }
        startInForeground(who)
        if (wakeLock == null) {
            wakeLock = runCatching {
                (getSystemService(POWER_SERVICE) as PowerManager)
                    .newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "carc:thinking")
                    .apply { acquire(WAKELOCK_TIMEOUT_MS) }
            }.onFailure { Log.w(TAG, "wakelock failed", it) }.getOrNull()
        }
        // START_NOT_STICKY: if the process is killed anyway there is nothing for a
        // restarted service to do — the ViewModel and the Python session are gone,
        // and the autosave is the recovery path.
        return START_NOT_STICKY
    }

    override fun onDestroy() {
        wakeLock?.let { if (it.isHeld) runCatching { it.release() } }
        wakeLock = null
        super.onDestroy()
    }

    private fun startInForeground(who: String) {
        val nm = getSystemService(NOTIFICATION_SERVICE) as NotificationManager
        nm.createNotificationChannel(
            NotificationChannel(
                CHANNEL_ID, "Opponent thinking",
                NotificationManager.IMPORTANCE_LOW,
            ).apply {
                description = "Shown while the opponent is choosing its move, so " +
                    "the search keeps running with the app in the background."
                setShowBadge(false)
            }
        )
        // Tapping the notification comes back to the game rather than starting a
        // second task: MainActivity is singleTop-by-default and restores its own
        // screen state, so the reorder-to-front flag is all this needs.
        val tap = PendingIntent.getActivity(
            this, 0,
            Intent(this, MainActivity::class.java)
                .addFlags(Intent.FLAG_ACTIVITY_REORDER_TO_FRONT),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
        )
        val notification = Notification.Builder(this, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.stat_notify_sync)
            .setContentTitle("$who thinking…")
            .setContentText("Keeping the search running while you are away.")
            .setContentIntent(tap)
            .setOngoing(true)
            .build()
        if (Build.VERSION.SDK_INT >= 34) {
            startForeground(NOTIF_ID, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC)
        } else {
            startForeground(NOTIF_ID, notification)
        }
    }

    companion object {
        private const val TAG = "CarcThinking"
        private const val CHANNEL_ID = "carc_thinking"
        private const val NOTIF_ID = 4243
        private const val EXTRA_OPPONENT = "opponent"

        /** Only ever used if the caller supplies no name at all. */
        private const val DEFAULT_WHO = "Opponent"

        /** A ceiling, not an expectation: a cold endgame solve is the worst case. */
        private const val WAKELOCK_TIMEOUT_MS = 15L * 60L * 1000L

        /**
         * Begin holding the process for [opponentName]'s turn.
         *
         * [opponentName] is the LIVE opponent's short display name — "Champion",
         * "Carcasum", "Tier-1" — never a hardcoded word, so the notification says
         * who is actually thinking.
         *
         * Silent on failure by design: a `ForegroundServiceStartNotAllowedException`
         * (the app was already backgrounded when the turn began) must cost the
         * scheduling boost, not the move.
         */
        fun start(context: Context, opponentName: String) {
            val intent = Intent(context, ThinkingService::class.java)
                .putExtra(EXTRA_OPPONENT, opponentName)
            runCatching { context.startForegroundService(intent) }
                .onFailure { Log.w(TAG, "could not start the thinking service", it) }
        }

        fun stop(context: Context) {
            runCatching { context.stopService(Intent(context, ThinkingService::class.java)) }
                .onFailure { Log.w(TAG, "could not stop the thinking service", it) }
        }
    }
}
