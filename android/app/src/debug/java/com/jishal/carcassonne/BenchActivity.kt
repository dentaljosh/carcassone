package com.jishal.carcassonne

import android.app.Activity
import android.graphics.Color
import android.os.Bundle
import android.view.View
import android.view.WindowManager

/**
 * DEBUG-ONLY trampoline for the battery bench (see BenchService). Renders a
 * black fullscreen view and holds the screen on so the app process sits in the
 * TOP-APP cpuset (all 8 cores) for the whole bench session — the same
 * scheduling class as real in-app play. With the screen off, Android caps a
 * shell-started foreground service to the background cpuset (little cores
 * only; verified 2026-08-16 on the SDK-37 preview), which silently measures a
 * different machine. It touches nothing game-related: no MainActivity, no
 * session resume, no files.
 */
class BenchActivity : Activity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setShowWhenLocked(true)
        setTurnScreenOn(true)
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        setContentView(View(this).apply { setBackgroundColor(Color.BLACK) })
    }
}
