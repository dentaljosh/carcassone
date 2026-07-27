package com.jishal.carcassonne

import androidx.activity.compose.BackHandler
import androidx.compose.animation.core.animate
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.rotate
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.IntSize
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import kotlin.math.roundToInt

/**
 * The play surface.
 *
 * Board transform (zoom/pan) is screen-local state, not ViewModel state: it is
 * pure presentation, it changes at 60 Hz during a pinch, and it must not
 * participate in the save file.
 */
@Composable
fun GameScreen(vm: GameViewModel, onExit: () -> Unit) {
    val ui by vm.ui.collectAsStateWithLifecycle()
    val assets by rememberTileAssets()
    val state = ui.state

    var transform by remember { mutableStateOf(BoardTransform()) }
    var viewW by remember { mutableStateOf(0f) }
    var viewH by remember { mutableStateOf(0f) }
    var confirmLeave by remember { mutableStateOf(false) }

    // Fit at game start (and on any new session / viewport change). Keyed on the
    // bridge generation, which is bumped by new_game / restore_game / reset.
    LaunchedEffect(state?.generation, viewW, viewH) {
        val st = state ?: return@LaunchedEffect
        if (viewW <= 0f || viewH <= 0f) return@LaunchedEffect
        val bounds = st.boundsWithMargin()?.atLeast(7) ?: return@LaunchedEffect
        transform = BoardTransform.fit(bounds, viewW, viewH)
    }

    // Gentle recentre after an AI move — ONLY when its tile landed off-screen,
    // so a champion move inside the current view never yanks the board.
    // Keyed on the cell alone, deliberately: keying on `turn` too would re-run
    // after every HUMAN move and chase the champion's stale last tile around.
    LaunchedEffect(state?.aiLastTile) {
        val cell = state?.aiLastTile ?: return@LaunchedEffect
        if (viewW <= 0f || viewH <= 0f) return@LaunchedEffect
        if (transform.isCellVisible(cell, viewW, viewH, margin = 12f)) return@LaunchedEffect
        val from = transform
        val to = BoardTransform.centeredOn(cell, from.scale, viewW, viewH)
        animate(0f, 1f, animationSpec = tween(320)) { f, _ ->
            transform = lerpTransform(from, to, f)
        }
    }

    BackHandler(enabled = true) {
        if (ui.thinking) confirmLeave = true else onExit()
    }

    Scaffold(
        topBar = { if (state != null) GameHud(ui, state, assets) },
    ) { insets ->
        Box(
            Modifier
                .fillMaxSize()
                .padding(insets),
        ) {
            when {
                state == null || assets == null -> LoadingPane(ui)
                else -> {
                    BoardCanvas(
                        state = state,
                        ghost = ui.ghost,
                        assets = assets!!,
                        transform = transform,
                        onTransform = { transform = it },
                        onCellTap = vm::onCellTap,
                        onMeepleSlot = vm::onMeepleSlot,
                        onViewportChanged = { w, h -> viewW = w; viewH = h },
                        modifier = Modifier.fillMaxSize(),
                    )
                    Column(
                        Modifier
                            .align(Alignment.BottomCenter)
                            .fillMaxWidth(),
                        horizontalAlignment = Alignment.End,
                    ) {
                        ActionButtons(ui, state, vm)
                        StatusBar(ui, state)
                    }
                    if (ui.thinking) {
                        ThinkingBanner(ui, state, Modifier.align(Alignment.TopCenter))
                    }
                    ui.error?.let { err ->
                        ErrorBanner(err, vm::clearError, Modifier.align(Alignment.TopCenter))
                    }
                }
            }
        }
    }

    val result = state?.result
    if (ui.showResult && result != null) {
        ResultDialog(
            result = result,
            opponentName = state.opponentName,
            onNewGame = { vm.dismissResult(); vm.rematch() },
            onHome = { vm.dismissResult(); onExit() },
        )
    }

    if (confirmLeave) {
        AlertDialog(
            onDismissRequest = { confirmLeave = false },
            title = { Text("Champion is thinking") },
            text = {
                Text(
                    "Leave anyway? The move will be discarded — the game resumes " +
                        "from your last position and the champion thinks again."
                )
            },
            confirmButton = {
                TextButton(onClick = {
                    confirmLeave = false
                    onExit()   // onExit -> vm.leaveGame(), which resets the bridge
                }) { Text("Leave") }
            },
            dismissButton = {
                TextButton(onClick = { confirmLeave = false }) { Text("Stay") }
            },
        )
    }
}

// --------------------------------------------------------------------------- //
// HUD                                                                          //
// --------------------------------------------------------------------------- //

@Composable
private fun GameHud(ui: GameUiState, state: GameState, assets: TileAssets?) {
    Surface(tonalElevation = 3.dp) {
        Row(
            Modifier
                .fillMaxWidth()
                .padding(horizontal = 12.dp, vertical = 8.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            ScoreChip("You", state.humanScore, state.humanMeeples, CarcColors.Human)
            ScoreChip(
                state.opponentName.take(14), state.aiScore, state.aiMeeples, CarcColors.Ai,
            )
            Spacer(Modifier.weight(1f))
            Column(horizontalAlignment = Alignment.End) {
                Text("${state.tilesRemaining} tiles", fontSize = 12.sp, fontWeight = FontWeight.Medium)
                Text("turn ${state.turn}", fontSize = 10.sp)
            }
            // The tile in hand, shown at the rotation the ghost is currently
            // aiming so the thumbnail and the board agree.
            if (state.isHumanTurn && state.isTilePhase && assets != null) {
                NextTileThumb(state, ui.ghost?.rotation ?: 0, assets)
            }
        }
    }
}

@Composable
private fun ScoreChip(label: String, score: Int, meeples: Int, colour: Color) {
    Box(
        Modifier
            .clip(RoundedCornerShape(8.dp))
            .background(colour.copy(alpha = 0.16f))
            .padding(horizontal = 8.dp, vertical = 4.dp),
    ) {
        Column {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Box(
                    Modifier
                        .size(8.dp)
                        .clip(RoundedCornerShape(4.dp))
                        .background(colour),
                )
                Spacer(Modifier.width(4.dp))
                Text(label, fontSize = 11.sp, fontWeight = FontWeight.Medium)
            }
            Text("$score", fontSize = 18.sp, fontWeight = FontWeight.Bold, color = colour)
            Text("$meeples meeple${if (meeples == 1) "" else "s"}", fontSize = 9.sp)
        }
    }
}

@Composable
private fun NextTileThumb(state: GameState, rotation: Int, assets: TileAssets) {
    val bmp = assets.tile(state.nextTile?.image) ?: return
    Canvas(Modifier.size(44.dp)) {
        // Same clockwise rule as the board (see drawTileArt).
        rotate(90f * rotation, pivot = Offset(size.width / 2f, size.height / 2f)) {
            drawImage(
                image = bmp,
                dstOffset = IntOffset.Zero,
                dstSize = IntSize(size.width.roundToInt(), size.height.roundToInt()),
            )
        }
    }
}

// --------------------------------------------------------------------------- //
// Overlays                                                                     //
// --------------------------------------------------------------------------- //

@Composable
private fun LoadingPane(ui: GameUiState) {
    Column(
        Modifier.fillMaxSize(),
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        CircularProgressIndicator()
        Spacer(Modifier.height(12.dp))
        Text(
            ui.error?.toString() ?: "Starting the champion…",
            style = MaterialTheme.typography.bodyMedium,
        )
    }
}

@Composable
private fun ThinkingBanner(ui: GameUiState, state: GameState, modifier: Modifier) {
    val p = ui.progress
    Card(modifier.padding(12.dp).fillMaxWidth()) {
        Column(Modifier.padding(12.dp)) {
            val elapsed = p?.elapsedS?.toInt() ?: 0
            Text(
                "${state.opponentName} is thinking… ${elapsed}s",
                fontWeight = FontWeight.Medium,
            )
            Spacer(Modifier.height(6.dp))
            // "exact" = the endgame solver has latched; the leaf counter stops
            // moving there, so a determinate bar would freeze and read as a hang.
            if (p != null && p.phase == "search" && p.fraction != null && p.expected > 0) {
                LinearProgressIndicator(
                    progress = { minOf(p.fraction, 0.99f) },
                    modifier = Modifier.fillMaxWidth(),
                )
                Text(
                    "${p.leafCalls} / ${p.expected} leaves",
                    fontSize = 10.sp,
                )
            } else {
                LinearProgressIndicator(Modifier.fillMaxWidth())
                Text(
                    if (p?.phase == "exact") "solving the endgame exactly" else "searching",
                    fontSize = 10.sp,
                )
            }
        }
    }
}

@Composable
private fun ErrorBanner(err: BridgeError, onDismiss: () -> Unit, modifier: Modifier) {
    Card(
        modifier.padding(12.dp).fillMaxWidth(),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.errorContainer,
        ),
    ) {
        Row(
            Modifier.padding(12.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(
                err.toString(),
                Modifier.weight(1f),
                fontSize = 12.sp,
                color = MaterialTheme.colorScheme.onErrorContainer,
            )
            TextButton(onClick = onDismiss) { Text("Dismiss") }
        }
    }
}

@Composable
private fun ActionButtons(ui: GameUiState, state: GameState, vm: GameViewModel) {
    if (!ui.canInteract) return
    val ghost = ui.ghost
    val showTileFabs = state.isTilePhase && ghost != null
    val showSkip = state.isMeeplePhase && state.legal.meeplePassId != null
    if (!showTileFabs && !showSkip) return

    Row(
        Modifier.padding(horizontal = 16.dp, vertical = 8.dp),
        horizontalArrangement = Arrangement.spacedBy(12.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        if (ghost != null && state.isTilePhase) {
            if (ghost.rotationCount > 1) {
                FloatingActionButton(onClick = vm::cycleRotation) { Text("⟳", fontSize = 22.sp) }
            }
            FloatingActionButton(onClick = vm::cancelPlacement) { Text("✗", fontSize = 22.sp) }
            FloatingActionButton(
                onClick = vm::confirmPlacement,
                containerColor = MaterialTheme.colorScheme.primary,
            ) { Text("✓", fontSize = 22.sp) }
        } else if (showSkip) {
            FloatingActionButton(onClick = vm::skipMeeple) {
                Text("Skip meeple", Modifier.padding(horizontal = 12.dp), fontSize = 14.sp)
            }
        }
    }
}

@Composable
private fun StatusBar(ui: GameUiState, state: GameState) {
    // `ui.ghost` has a custom getter, so it is read into a local before use
    // (no smart cast on a property getter).
    val ghost = ui.ghost
    val text = when {
        state.isTerminated -> state.result?.verdict ?: "Game over."
        ui.thinking -> "${state.opponentName} is thinking…"
        ui.busy -> "…"
        !state.isHumanTurn -> "${state.opponentName}'s turn"
        state.isTilePhase && ghost != null ->
            "Rotation ${ghost.rotation} of ${ghost.rotationCount} — ✓ to place, ⟳ to rotate"
        state.isTilePhase -> "Your move — tap a highlighted square to place the tile"
        state.isMeeplePhase -> "Place a meeple, or skip"
        else -> ""
    }
    val last = state.aiLastMove
    Surface(
        Modifier.fillMaxWidth(),
        tonalElevation = 3.dp,
    ) {
        Column(Modifier.padding(horizontal = 12.dp, vertical = 6.dp)) {
            Text(text, fontSize = 13.sp, fontWeight = FontWeight.Medium)
            if (last != null) {
                val secs = last.elapsedS?.let { " (${"%.1f".format(it)}s)" } ?: ""
                Text("Last champion move: ${last.describe}$secs", fontSize = 10.sp)
            }
            state.budgetNote?.let {
                Text(it, fontSize = 10.sp, color = MaterialTheme.colorScheme.error)
            }
        }
    }
}

@Composable
private fun ResultDialog(
    result: GameResult,
    opponentName: String,
    onNewGame: () -> Unit,
    onHome: () -> Unit,
) {
    AlertDialog(
        onDismissRequest = { },
        title = { Text(result.verdict) },
        text = {
            Column {
                Text("Final score  ${result.scores.joinToString(" – ")}")
                Text(
                    if (result.diff == 0) "A dead heat."
                    else "Margin: ${result.diff} point${if (result.diff == 1) "" else "s"}",
                )
                Spacer(Modifier.height(8.dp))
                Text("Opponent: $opponentName", fontSize = 12.sp)
                result.budgetNote?.let {
                    Spacer(Modifier.height(8.dp))
                    Text(it, color = MaterialTheme.colorScheme.error, fontSize = 12.sp)
                }
            }
        },
        confirmButton = { TextButton(onClick = onNewGame) { Text("New game") } },
        dismissButton = { TextButton(onClick = onHome) { Text("Back to home") } },
    )
}
