package com.jishal.carcassonne

import android.content.res.Configuration
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.BackHandler
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawing
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalConfiguration
import androidx.lifecycle.viewmodel.compose.viewModel

/**
 * Single activity, three destinations.
 *
 * Plain state-based navigation rather than Navigation-Compose: there are three
 * screens and no deep links or argument passing, and the one thing that really
 * must survive — the game — lives in an activity-scoped [GameViewModel] (and,
 * underneath it, the Python session and the autosave file), not in a back stack.
 */
private enum class Screen { HOME, GAME, SETTINGS, DEBUG, PAST_GAMES }

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            CarcTheme {
                Surface(
                    modifier = Modifier.fillMaxSize(),
                    color = MaterialTheme.colorScheme.background,
                ) {
                    CarcApp()
                }
            }
        }
    }
}

@Composable
private fun CarcApp() {
    // Activity-scoped: the same instance backs Home and Game, so navigating home
    // mid-game leaves the session (and the in-flight AI turn) exactly as it was.
    val vm: GameViewModel = viewModel()
    var screen by rememberSaveable { mutableStateOf(Screen.HOME) }

    // Every navigation drops a stale error. A BridgeError is about the operation
    // that just failed, not about the app, so carrying it across a screen change
    // left Home showing an error banner for something the user had already moved
    // on from (and, on Home, with no context left to interpret it).
    fun navigate(to: Screen) {
        vm.clearError()
        screen = to
    }

    when (screen) {
        Screen.HOME -> HomeScreen(
            vm = vm,
            onPlay = { screen = Screen.GAME },
            onSettings = { navigate(Screen.SETTINGS) },
            onDebug = { navigate(Screen.DEBUG) },
            onPastGames = { navigate(Screen.PAST_GAMES) },
        )

        Screen.PAST_GAMES -> {
            BackHandler { navigate(Screen.HOME) }
            PastGamesScreen(vm = vm, onBack = { navigate(Screen.HOME) })
        }

        Screen.SETTINGS -> SettingsScreen(
            vm = vm,
            onBack = { navigate(Screen.HOME) },
        )

        Screen.GAME -> GameScreen(
            vm = vm,
            onExit = {
                // No-op when nothing is in flight (the session is kept and the
                // Game screen reopens exactly as it was); tears the session down
                // when a bridge call is still running.
                vm.leaveGame()
                vm.refreshSaveSlot()
                navigate(Screen.HOME)
            },
        )

        Screen.DEBUG -> {
            BackHandler { navigate(Screen.HOME) }
            // safeDrawing (not the Scaffold default systemBars) so a display
            // cutout in landscape also keeps its distance.
            Scaffold(contentWindowInsets = WindowInsets.safeDrawing) { insets ->
                Column(Modifier.fillMaxSize().padding(insets)) {
                    TextButton(onClick = { navigate(Screen.HOME) }) { Text("← Home") }
                    // The shared game VM, so the debug fast-forward acts on the
                    // session the Game screen is actually holding.
                    DebugScreen(gameVm = vm)
                }
            }
        }
    }
}

@Composable
private fun CarcTheme(content: @Composable () -> Unit) {
    val dark = (LocalConfiguration.current.uiMode and Configuration.UI_MODE_NIGHT_MASK) ==
        Configuration.UI_MODE_NIGHT_YES
    MaterialTheme(
        colorScheme = if (dark) darkColorScheme() else lightColorScheme(),
        content = content,
    )
}
