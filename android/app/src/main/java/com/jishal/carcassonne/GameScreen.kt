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
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.WindowInsetsSides
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.only
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawing
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.windowInsetsPadding
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
import androidx.compose.runtime.MutableState
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
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.IntSize
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import java.util.Locale
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

    // Held as the state object (not just the delegated value) so the recentre
    // animation can be a plain function shared by the AI and human paths.
    val transformState = remember { mutableStateOf(BoardTransform()) }
    var transform by transformState
    var viewW by remember { mutableStateOf(0f) }
    var viewH by remember { mutableStateOf(0f) }
    var confirmLeave by remember { mutableStateOf(false) }

    // The board canvas runs the full height of the content area, with the action
    // buttons + status bar floating over its bottom edge and the banners over its
    // top. Those strips are not usable board, so the auto-recentre must not count
    // them as "visible" — see BoardTransform.isCellVisible.
    //
    // The canvas is deliberately full-bleed at the bottom (it draws under the
    // gesture pill), so the unusable bottom strip is the chrome PLUS that system
    // inset — the chrome is pushed up by exactly that much.
    val density = LocalDensity.current
    val bottomSystemPx = WindowInsets.safeDrawing.getBottom(density).toFloat()
    val insetTopPx = with(density) { TOP_OVERLAY.toPx() }
    val insetBottomPx = with(density) { BOTTOM_OVERLAY.toPx() } + bottomSystemPx

    // Process death while on the Game screen: MainActivity restores `screen = GAME`
    // from the saved instance state, but the ViewModel — and with it the Python
    // session — is gone, so `state` is null with nothing in flight that would ever
    // fill it and the LoadingPane would spin forever. Any game that was in progress
    // has an autosave (it is written after every applied action), so resume it;
    // if there genuinely is none, go home rather than sit on the spinner.
    LaunchedEffect(Unit) {
        if (ui.state == null && !ui.busy && !ui.opActive && !ui.warmingUp &&
            ui.error == null
        ) {
            if (vm.hasSavedGame()) vm.resume() else onExit()
        }
    }

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
        recentreIfOffscreen(
            state?.aiLastTile, transformState, viewW, viewH, insetTopPx, insetBottomPx,
        )
    }

    // ...and after a HUMAN placement too. A tapped cell is by definition on
    // screen, but it can be right at the edge — `isCellVisible`'s margin treats
    // that as off-screen, so the board eases over and the newly opened
    // neighbours become reachable without a manual pan.
    LaunchedEffect(ui.lastHumanTile) {
        recentreIfOffscreen(
            ui.lastHumanTile, transformState, viewW, viewH, insetTopPx, insetBottomPx,
        )
    }

    // Gated on isInFlight(), the same predicate leaveGame() uses to decide whether
    // to tear the session down. When the two disagreed (this read `ui.thinking`),
    // a Back pressed mid-apply exited silently AND kept the session.
    BackHandler(enabled = true) {
        if (vm.isInFlight()) confirmLeave = true else onExit()
    }

    Scaffold(
        topBar = { if (state != null) GameHud(ui, state, assets) },
        // Zero, on purpose: the board must stay full-bleed. The HUD in the top bar
        // slot insets ITSELF against the status bar, and the floating bottom chrome
        // insets itself against the navigation bar — the canvas between them keeps
        // every pixel.
        contentWindowInsets = WindowInsets(0),
    ) { insets ->
        Box(
            Modifier
                .fillMaxSize()
                .padding(insets),
        ) {
            when {
                // A fatal error before any board arrived (bad restore, bridge import
                // failure): the spinner would never stop, so show the error and a way
                // out instead.
                ui.error != null && state == null -> FatalPane(ui.error!!, onExit)
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
                            .fillMaxWidth()
                            // The board draws under the gesture pill; its chrome
                            // must not. Horizontal too, for a landscape nav bar
                            // or a cutout.
                            .windowInsetsPadding(
                                WindowInsets.safeDrawing.only(
                                    WindowInsetsSides.Bottom + WindowInsetsSides.Horizontal,
                                ),
                            ),
                        horizontalAlignment = Alignment.End,
                    ) {
                        // The champion's turn failed. It is not the human's turn, so
                        // ActionButtons is empty and there would otherwise be nothing
                        // to press — the seat is simply stuck. Offer the turn again.
                        if (ui.aiFailed) {
                            Row(
                                Modifier.padding(horizontal = 16.dp, vertical = 8.dp),
                            ) {
                                FloatingActionButton(
                                    onClick = vm::retryAiTurn,
                                    containerColor = MaterialTheme.colorScheme.primary,
                                ) {
                                    Text(
                                        "Retry champion move",
                                        Modifier.padding(horizontal = 16.dp),
                                        fontSize = 14.sp,
                                    )
                                }
                            }
                        }
                        ActionButtons(ui, state, vm)
                        StatusBar(ui, state)
                    }
                    // The banners hang below the HUD, which has already cleared the
                    // status bar; only the horizontal sides are still theirs to dodge.
                    val bannerModifier = Modifier
                        .align(Alignment.TopCenter)
                        .windowInsetsPadding(
                            WindowInsets.safeDrawing.only(WindowInsetsSides.Horizontal),
                        )
                    if (ui.thinking) {
                        ThinkingBanner(ui, state, bannerModifier)
                    }
                    ui.error?.let { err ->
                        ErrorBanner(err, vm::clearError, bannerModifier)
                    }
                    ui.saveMismatch?.let { note ->
                        MismatchBanner(note, vm::dismissSaveMismatch, bannerModifier)
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
            humanPlayer = state.humanPlayer,
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

/** Compact seconds: one decimal under 10s, whole seconds above (a "~12.3s" ETA
 *  implies a precision the rolling mean does not have). */
internal fun formatSeconds(seconds: Double): String =
    if (seconds < 10.0) "%.1fs".format(Locale.US, seconds)
    else "%.0fs".format(Locale.US, seconds)

/**
 * The HUD's game-progress read-out.
 *
 * These replace the old `turn N`, which printed the bridge's `turn` field — a
 * count of every APPLIED ACTION, bumped once per phase per seat (and once more
 * for each auto-passed forced move). Placing a tile and then deciding its meeple
 * are two separate actions, so between two consecutive human views the number
 * jumped unevenly — 2 → 3 → 6 → 7 → 10 → 11 → 14 was a real game — and read like
 * a turn counter dropping numbers. Nothing in the state maps to a "turn" the
 * player would recognise, so the HUD now reports the two quantities that are
 * unambiguous and directly countable on the board.
 *
 * [tilesRemaining] is the bridge's `k_remaining` — undrawn deck plus the tile in
 * hand — and [placed] is simply how many tiles are on the board, so neither needs
 * a hardcoded deck size to be honest.
 */
internal fun tilesLeftLabel(tilesRemaining: Int): String =
    "$tilesRemaining tile${if (tilesRemaining == 1) "" else "s"} left"

internal fun tilesPlacedLabel(placed: Int): String = "$placed placed"

/**
 * Approximate heights of the chrome floating over the board canvas: the banner
 * strip at the top, and the action-button row plus status bar at the bottom.
 *
 * Fixed dp rather than measured values on purpose — this only decides *whether* to
 * ease the board towards a cell, so being a few dp out never produces a visibly
 * wrong result, and threading real measurements through would mean hoisting layout
 * state out of two child composables for no gain.
 */
private val TOP_OVERLAY = 96.dp
private val BOTTOM_OVERLAY = 132.dp

/**
 * Ease the board so [cell] is centred — but only when it is not comfortably in
 * view already. A no-op for a null cell, a zero viewport, or a cell that is
 * already visible, so both callers can invoke it unconditionally.
 */
private suspend fun recentreIfOffscreen(
    cell: Cell?,
    transformState: MutableState<BoardTransform>,
    viewW: Float,
    viewH: Float,
    insetTop: Float,
    insetBottom: Float,
) {
    if (cell == null || viewW <= 0f || viewH <= 0f) return
    val from = transformState.value
    if (from.isCellVisible(
            cell, viewW, viewH, margin = 12f,
            insetTop = insetTop, insetBottom = insetBottom,
        )
    ) return
    val to = BoardTransform.centeredOn(cell, from.scale, viewW, viewH)
    animate(0f, 1f, animationSpec = tween(320)) { f, _ ->
        transformState.value = lerpTransform(from, to, f)
    }
}

// --------------------------------------------------------------------------- //
// HUD                                                                          //
// --------------------------------------------------------------------------- //

@Composable
private fun GameHud(ui: GameUiState, state: GameState, assets: TileAssets?) {
    // The inset goes on the Row, not the Surface: the Surface keeps painting its
    // tonal background all the way up behind the status bar (so the clock sits on
    // the HUD's colour, not on a torn edge), while the content starts below it.
    Surface(tonalElevation = 3.dp) {
        Row(
            Modifier
                .fillMaxWidth()
                .windowInsetsPadding(
                    WindowInsets.safeDrawing.only(
                        WindowInsetsSides.Top + WindowInsetsSides.Horizontal,
                    ),
                )
                .padding(horizontal = 12.dp, vertical = 8.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            ScoreChip("You", state.humanScore, state.humanMeeples, CarcColors.Human)
            // A weakened preset names itself "Champion(weakened k4x172)", which a
            // 14-char chip renders as "Champion(weake". The chip drops the
            // parenthetical; the full name (and the budget note) stay in the status
            // bar and the end-of-game dialog, where the warning belongs.
            ScoreChip(
                state.opponentName.substringBefore('(').trim().take(14),
                state.aiScore, state.aiMeeples, CarcColors.Ai,
            )
            Spacer(Modifier.weight(1f))
            Column(horizontalAlignment = Alignment.End) {
                Text(
                    tilesLeftLabel(state.tilesRemaining),
                    fontSize = 12.sp,
                    fontWeight = FontWeight.Medium,
                    maxLines = 1,
                    softWrap = false,
                )
                Text(
                    tilesPlacedLabel(state.board.size),
                    fontSize = 10.sp,
                    maxLines = 1,
                    softWrap = false,
                )
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
        // No HUD is composed while `state` is null, so these two panes are the
        // only thing on screen and must inset themselves.
        Modifier.fillMaxSize().safeDrawingPadding(),
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

/** Terminal state with no board to fall back to — the spinner would never stop. */
@Composable
private fun FatalPane(err: BridgeError, onHome: () -> Unit) {
    Column(
        Modifier.fillMaxSize().safeDrawingPadding().padding(24.dp),
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Text("Could not start the game", style = MaterialTheme.typography.titleMedium)
        Spacer(Modifier.height(8.dp))
        Text(
            err.toString(),
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.error,
        )
        Spacer(Modifier.height(16.dp))
        TextButton(onClick = onHome) { Text("Back to home") }
    }
}

/** The restored save was stamped with a different champion build (advisory). */
@Composable
private fun MismatchBanner(note: String, onDismiss: () -> Unit, modifier: Modifier) {
    Card(
        modifier.padding(12.dp).fillMaxWidth(),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.secondaryContainer,
        ),
    ) {
        Row(Modifier.padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
            Text(
                note,
                Modifier.weight(1f),
                fontSize = 12.sp,
                color = MaterialTheme.colorScheme.onSecondaryContainer,
            )
            TextButton(onClick = onDismiss) { Text("OK") }
        }
    }
}

@Composable
private fun ThinkingBanner(ui: GameUiState, state: GameState, modifier: Modifier) {
    val p = ui.progress
    Card(modifier.padding(12.dp).fillMaxWidth()) {
        Column(Modifier.padding(12.dp)) {
            val elapsed = p?.elapsedS?.toInt() ?: 0
            // The ETA is a rolling mean of this session's last few moves, so it
            // is only shown once there IS one — never a guess from the preset.
            val eta = ui.etaSeconds?.let { " of ~${formatSeconds(it)}" } ?: ""
            Text(
                "${state.opponentName} is thinking… ${elapsed}s$eta",
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
        ui.aiFailed -> "The champion's move failed — retry, or press Back to leave."
        ui.thinking -> "${state.opponentName} is thinking…"
        ui.busy -> "…"
        !state.isHumanTurn -> "${state.opponentName}'s turn"
        state.isTilePhase && ghost != null ->
            // 1-based POSITION in the legal list, not the raw engine rotation value:
            // the legal set is often sparse ({1,3}), which printed as "Rotation 3 of 2".
            "Rotation ${ghost.index + 1} of ${ghost.rotationCount} — ✓ to place, ⟳ to rotate"
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
    humanPlayer: Int,
    onNewGame: () -> Unit,
    onHome: () -> Unit,
) {
    // `result.scores` is in ENGINE SEAT order (index 0 = player 0), while the HUD
    // always puts the human chip first. Printing the raw list therefore reversed the
    // reading whenever the human sat in seat 1. Label the seats instead.
    val you = result.scores.getOrElse(humanPlayer) { 0 }
    val them = result.scores.getOrElse(1 - humanPlayer) { 0 }
    // Same parenthetical trim as the HUD chip; the full name is printed below.
    val themLabel = opponentName.substringBefore('(').trim().ifEmpty { "Champion" }
    AlertDialog(
        onDismissRequest = { },
        title = { Text(result.verdict) },
        text = {
            Column {
                Text("Final score  You $you – $them $themLabel")
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
