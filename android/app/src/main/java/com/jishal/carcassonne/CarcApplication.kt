package com.jishal.carcassonne

import android.app.Application
import android.util.Log
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform

/**
 * Starts the embedded CPython runtime exactly once, before anything can touch
 * [PythonBridge]. Chaquopy's own ContentProvider handles extraction of the
 * stdlib/assets; [Python.start] only needs to be called if it hasn't already.
 */
class CarcApplication : Application() {

    override fun onCreate() {
        super.onCreate()
        if (!Python.isStarted()) {
            Log.i(TAG, "Starting Chaquopy AndroidPlatform")
            Python.start(AndroidPlatform(this))
        }
        Log.i(TAG, "Chaquopy started")
    }

    companion object {
        const val TAG = "CarcApp"
    }
}
