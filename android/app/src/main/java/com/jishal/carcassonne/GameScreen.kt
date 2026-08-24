package com.jishal.carcassonne

import android.content.res.Configuration
import androidx.activity.compose.BackHandler
import androidx.compose.animation.core.animate
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
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
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.only
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawing
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
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
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.rotate
import androidx.compose.ui.layout.onGloballyPositioned
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.IntSize
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import kotlinx.coroutines.launch
import java.util.Locale
import kotlin.math.roundToInt

/**
 * The play surface.
 *
 * Board transform (zoom/pan) is screen-local state, not ViewModel state: it is
 * pure presentation, it changes at 60 Hz during a pinch, and it must not
 * participate in the save file.
 *
 * ### The camera
 *
 * There are four ways the view moves, in descending priority:
 *
 * 1. **The player** — pinch/pan (and double-tap on empty board). Always wins,
 *    and sets [CameraPolicy.userAdjusted] so the automatic rules back off.
 * 2. **Fit at game start** — instant, on a new session or a viewport change.
 * 3. **Settle after a placement** — the *only* automatic motion during play, and
 *    it fires only when something is genuinely not visible: either the board has
 *    outgrown the viewport (re-fit) or the tile that just landed is off-screen
 *    (recentre). Keyed on placements, never on interaction, so it cannot yank the
 *    board while a finger is down.
 * 4. **Meeple close-up** — a one-off zoom onto the tile whose slots are being
 *    offered, when they would otherwise be a few pixels apart, undone when the
 *    sub-phase ends.
 *
 * All of it runs in ONE effect so the four rules can never animate against each
 * other; each step suspends until its animation finishes.
 */
@Composable
fun GameScreen(vm: GameViewModel, onExit: () -> Unit) {
    val ui by vm.ui.collectAsStateWithLifecycle()
    val assets by rememberTileAssets()
    val state = ui.state
    val scope = rememberCoroutineScope()

    // Held as the state object (not just the delegated value) so the camera
    // animations can be plain suspend functions shared by every path.
    val transformState = remember { mutableStateOf(BoardTransform()) }
    var transform by transformState
    val camera = remember { CameraPolicy() }
    var viewW by remember { mutableStateOf(0f) }
    var viewH by remember { mutableStateOf(0f) }
    var confirmLeave by remember { mutableStateOf(false) }

    val landscape =
        LocalConfiguration.current.orientation == Configuration.ORIENTATION_LANDSCAPE

    // The board canvas runs the full height of the content area, with the action
    // buttons + status bar floating over its bottom edge. That strip is not usable
    // board, so every fit/visibility decision must subtract it — see
    // BoardTransform.isBoundsVisible.
    //
    // MEASURED, not guessed. The old fixed 132dp estimate was tuned by eye in
    // portrait; in landscape the same chrome is a much larger share of a much
    // shorter viewport, and fitting to the full height left the bottom rows of the
    // board underneath the status panel with no way to see them.
    //
    // Held as a RUNNING MAXIMUM because the strip's height is not constant: the
    // action-button row appears the moment a ghost is aimed and vanishes when it
    // is played. Feeding that raw into the fit would re-fit the board twice per
    // turn, trading one camera bug for a worse one. The max settles after a single
    // turn at "status bar + buttons", which is the height the board must clear
    // anyway.
    //
    // Scoped to the orientation (`remember(landscape)`), because the two layouts
    // have genuinely different chrome and carrying portrait's taller strip into
    // landscape would waste a third of a 1080px-high viewport.
    //
    // Reported via onGloballyPositioned, NOT onSizeChanged: the activity handles
    // rotation itself (see AndroidManifest `configChanges`), so this state
    // survives the flip and is re-initialised by the `remember` key — but
    // onSizeChanged only fires when the size CHANGES, and after a re-init the
    // strip's height often has not. That combination silently left landscape
    // fitting to the full canvas, i.e. straight back into the bug being fixed.
    var bottomChromePx by remember(landscape) { mutableStateOf(0f) }

    // The top banners (thinking / error / save-mismatch) are deliberately NOT part
    // of this. They are transient and, in the case of the one that is up the
    // longest, they cover the board precisely while the opponent is thinking and
    // the player cannot act. Reserving their height permanently would shrink the
    // board on every screen for a strip that is usually not there.

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
    //
    // It is also keyed on the chrome measurement, because the first composition
    // does not know it yet — but a chrome re-measure is NOT a new game, so it must
    // not overrule a player who has meanwhile taken the camera. Hence the
    // generation guard: only a genuinely new session resets the camera policy.
    LaunchedEffect(state?.generation, viewW, viewH, bottomChromePx) {
        val st = state ?: return@LaunchedEffect
        if (viewW <= 0f || viewH <= 0f) return@LaunchedEffect
        val newSession = st.generation != camera.fittedGeneration
        if (camera.userAdjusted && !newSession) return@LaunchedEffect
        // Same reasoning for the meeple close-up, which owns the camera until the
        // sub-phase ends (settleCamera's rule 3 already stands aside for it). Without
        // this, entering the meeple phase while the chrome is still settling — a
        // Resume that lands straight in it — re-fits the board a frame after the
        // close-up zoomed, and the player is handed back the tiny targets the
        // close-up exists to avoid.
        if (camera.preMeeple != null && !newSession) return@LaunchedEffect
        val bounds = st.boundsWithMargin()?.atLeast(7) ?: return@LaunchedEffect
        transform = BoardTransform.fit(bounds, viewW, viewH, insetBottom = bottomChromePx)
        camera.userAdjusted = false
        if (newSession) {
            camera.preMeeple = null
            camera.fittedGeneration = st.generation
        }
    }

    // The subject of the meeple sub-phase, or null when it is not open. Its slots
    // can be a quarter of a tile apart, so at a whole-board fit they are a handful
    // of pixels from each other — hence the close-up in [settleCamera].
    val meepleFocus = state?.legal?.meepleTarget
        ?.takeIf { state.isHumanTurn && state.isMeeplePhase && state.legal.meepleSlots.isNotEmpty() }

    // Rules 3 and 4, in one place so they run in order rather than in parallel.
    LaunchedEffect(
        ui.lastPlacedTile, state?.board?.size, meepleFocus, viewW, viewH, bottomChromePx,
    ) {
        val st = state ?: return@LaunchedEffect
        settleCamera(
            state = st,
            focus = ui.lastPlacedTile,
            meepleFocus = meepleFocus,
            transformState = transformState,
            camera = camera,
            viewW = viewW, viewH = viewH,
            insetTop = 0f, insetBottom = bottomChromePx,
        )
    }

    // Gated on isInFlight(), the same predicate leaveGame() uses to decide whether
    // to tear the session down. When the two disagreed (this read `ui.thinking`),
    // a Back pressed mid-apply exited silently AND kept the session.
    BackHandler(enabled = true) {
        if (vm.isInFlight()) confirmLeave = true else onExit()
    }

    // The dialog's whole premise is "a search is running that Leave would throw
    // away". Searches finish on their own — at Instant they finish almost at once —
    // and the dialog then sat there asking about nothing, with a Leave button whose
    // warning text ("the move will be discarded") had become false. Close it the
    // moment the premise expires; the player keeps the move and stays in the game.
    LaunchedEffect(ui.thinking, ui.opActive) {
        if (confirmLeave && !ui.thinking && !ui.opActive) confirmLeave = false
    }

    Scaffold(
        topBar = {
            if (state != null) {
                GameHud(
                    ui, state, assets, landscape,
                    onFit = {
                        scope.launch {
                            fitNow(
                                state, transformState, camera,
                                viewW, viewH, 0f, bottomChromePx,
                            )
                        }
                    },
                    onOpenBag = vm::openBag,
                )
            }
        },
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
                        onTransform = { transform = it; camera.userAdjusted = true },
                        onCellTap = vm::onCellTap,
                        onMeepleSlot = vm::onMeepleSlot,
                        onDoubleTap = { sx, sy ->
                            scope.launch {
                                toggleZoom(
                                    state, transformState, camera, sx, sy,
                                    viewW, viewH, 0f, bottomChromePx,
                                )
                            }
                        },
                        onViewportChanged = { w, h -> viewW = w; viewH = h },
                        modifier = Modifier.fillMaxSize(),
                        ghostPreview = ui.ghostPreview,
                        ownership = ui.ownership,
                        pendingSlot = ui.selectedSlot,
                    )

                    Column(
                        Modifier
                            .align(Alignment.BottomCenter)
                            // OUTERMOST of the size-affecting modifiers, so the
                            // measurement includes the inset padding below — the
                            // canvas is full-bleed under the gesture pill, so that
                            // padding is unusable board too.
                            .onGloballyPositioned {
                                bottomChromePx = maxOf(bottomChromePx, it.size.height.toFloat())
                            }
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
                                        "Retry ${MoveText.shortOpponent(state.opponentName)} move",
                                        Modifier.padding(horizontal = 16.dp),
                                        fontSize = 14.sp,
                                    )
                                }
                            }
                        }
                        ActionButtons(ui, state, vm)
                        StatusBar(ui, state, landscape)
                    }

                    // The banners hang below the HUD, which has already cleared the
                    // status bar; only the horizontal sides are still theirs to dodge.
                    // Stacked in one column (they used to be three independent
                    // TopCenter children, which overlapped when two were up at once)
                    // and measured as a unit for the fit inset.
                    Column(
                        Modifier
                            .align(Alignment.TopCenter)
                            .windowInsetsPadding(
                                WindowInsets.safeDrawing.only(WindowInsetsSides.Horizontal),
                            ),
                    ) {
                        if (ui.lastEvents.isNotEmpty()) {
                            LastMoveChip(ui.lastEvents, vm::dismissEvents, Modifier)
                        }
                        if (ui.thinking) ThinkingBanner(ui, state, Modifier)
                        ui.error?.let { err -> ErrorBanner(err, vm::clearError, Modifier) }
                        ui.saveMismatch?.let { note ->
                            MismatchBanner(note, vm::dismissSaveMismatch, Modifier)
                        }
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

    if (ui.showBag) {
        BagDialog(ui.bag, assets, vm::closeBag)
    }

    if (confirmLeave) {
        AlertDialog(
            onDismissRequest = { confirmLeave = false },
            title = { Text("${MoveText.shortOpponent(state?.opponentName ?: "")} is thinking") },
            text = {
                Text(
                    "Leave anyway? The move will be discarded — the game resumes " +
                        "from your last position and the opponent thinks again."
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
 * [tilesRemaining] is [GameState.tilesLeft] — NOT the raw bridge field, which
 * double-counts the tile in hand for the whole meeple sub-phase — and [placed] is
 * simply how many tiles are on the board, so the two always sum to the deck size
 * and neither needs that size hardcoded to be honest.
 */
internal fun tilesLeftLabel(tilesRemaining: Int): String =
    "$tilesRemaining tile${if (tilesRemaining == 1) "" else "s"} left"

internal fun tilesPlacedLabel(placed: Int): String = "$placed placed"

// --------------------------------------------------------------------------- //
// Camera                                                                       //
// --------------------------------------------------------------------------- //

/** Comfort slack, in px, before a cell counts as "off-screen". */
private const val FOCUS_MARGIN = 12f

/** Comfort slack for the whole-board test. Smaller, so a board that merely
 *  touches the edges is not re-fitted every single move. */
private const val BOARD_MARGIN = 4f

/**
 * Below this scale the meeple slots are too close together to aim at.
 *
 * Calibrated on device, not guessed: adjacent slots are a quarter-tile apart, so
 * at the opening fit (scale ~1.5 on a 1080px phone) they are only ~38px — about
 * 13dp — from each other, well under the 48dp minimum. The trigger therefore has
 * to sit ABOVE the natural whole-board scale or the close-up never fires when it
 * is most needed.
 */
private const val MEEPLE_ZOOM_TRIGGER = 3.6f

/**
 * ...and this is where the close-up takes them.
 *
 * Was 2.3, which put a quarter-tile gap at ~58px (~21dp) — better than the fit, still
 * under half a Material touch target, and mis-taps between adjacent farmer corners
 * were the single most reported annoyance of playing on the phone. At 4.2 the same
 * gap is 105px (~40dp) and the tile fills roughly a quarter of the screen, which is
 * the right framing for a decision about one tile. The old ceiling of 3.0 could not
 * express this at all — see [MAX_SCALE].
 */
private const val MEEPLE_ZOOM_TARGET = 4.2f

/** Double-tap zoom-in factor, relative to the whole-board fit. */
private const val DOUBLE_TAP_FACTOR = 2f

/** What the automatic camera should do after a placement. */
internal enum class CameraMove { NONE, REFIT, RECENTRE }

/**
 * The automatic-camera rule table, as a pure function so it can be pinned by a
 * JVM test instead of only by playing a game.
 *
 * Read it as a priority list:
 *
 *  * the board no longer fits **and** either the player has not taken the camera
 *    or the move they just made is out of sight → **re-fit**. The second half is
 *    what stops manual control from becoming a trap: once the camera has to move
 *    anyway, fitting is strictly better than panning blind;
 *  * the board fits but the new tile is off-screen (or tucked under the chrome)
 *    → **recentre** at the current scale, the original round-1 behaviour;
 *  * otherwise → **nothing**. Doing nothing is the common case and the whole
 *    reason this is a decision function rather than an unconditional fit.
 */
internal fun cameraDecision(
    boardVisible: Boolean,
    focusVisible: Boolean,
    userAdjusted: Boolean,
    hasFocus: Boolean,
): CameraMove = when {
    !boardVisible && (!userAdjusted || !focusVisible) -> CameraMove.REFIT
    !focusVisible && hasFocus -> CameraMove.RECENTRE
    else -> CameraMove.NONE
}

/** Mutable, non-composable camera bookkeeping. Not `State`: nothing recomposes
 *  on it, and making it observable would only invite a recomposition loop. */
private class CameraPolicy {
    /** The player has pinched, panned or double-tapped since the last automatic
     *  fit. Suppresses the *re-fit* rule (but not the off-screen recentre — if the
     *  camera has to move anyway, moving it to a good place is strictly better). */
    var userAdjusted: Boolean = false

    /** Where the view was before the meeple close-up, to be restored after. */
    var preMeeple: BoardTransform? = null

    /** The bridge generation the opening fit was taken for. Distinguishes "a new
     *  game started" from "the chrome re-measured", which look identical to a
     *  LaunchedEffect key but must not be treated the same. */
    var fittedGeneration: Int = -1
}

private suspend fun animateTransform(
    transformState: MutableState<BoardTransform>,
    to: BoardTransform,
    durationMs: Int = 320,
) {
    val from = transformState.value
    animate(0f, 1f, animationSpec = tween(durationMs)) { f, _ ->
        transformState.value = lerpTransform(from, to, f)
    }
}

/**
 * The whole automatic-camera policy, run after every placement (and whenever the
 * meeple sub-phase opens or closes).
 *
 * The bug this replaces: the fit ran **once**, at game start, and the only rule
 * during play was "recentre on the AI's tile if it landed off-screen" — which
 * pans at the *current* scale. So the board grew, the scale never followed, and
 * by ~50 tiles half the position was off-screen or behind the status panel with
 * no in-game way to get it back.
 */
private suspend fun settleCamera(
    state: GameState,
    focus: Cell?,
    meepleFocus: Cell?,
    transformState: MutableState<BoardTransform>,
    camera: CameraPolicy,
    viewW: Float,
    viewH: Float,
    insetTop: Float,
    insetBottom: Float,
) {
    if (viewW <= 0f || viewH <= 0f) return

    // -- rule 3: keep the board visible -------------------------------------
    // Skipped while the meeple close-up is up: the view is deliberately zoomed in
    // on one tile, and re-fitting here would fight it. The restore below hands
    // control back.
    if (camera.preMeeple == null) {
        val from = transformState.value
        val placed = BoardBounds.of(state.board.map { it.cell })
        val decision = cameraDecision(
            boardVisible = placed == null || from.isBoundsVisible(
                placed, viewW, viewH, BOARD_MARGIN, insetTop, insetBottom,
            ),
            focusVisible = focus == null || from.isCellVisible(
                focus, viewW, viewH, FOCUS_MARGIN, insetTop, insetBottom,
            ),
            userAdjusted = camera.userAdjusted,
            hasFocus = focus != null,
        )
        when (decision) {
            CameraMove.REFIT -> {
                val bounds = state.boundsWithMargin()?.atLeast(7)
                if (bounds != null) {
                    animateTransform(
                        transformState,
                        BoardTransform.fit(bounds, viewW, viewH, insetTop, insetBottom),
                    )
                    camera.userAdjusted = false
                }
            }
            CameraMove.RECENTRE -> animateTransform(
                transformState,
                BoardTransform.centeredOn(
                    focus!!, from.scale, viewW, viewH, insetTop, insetBottom,
                ),
            )
            CameraMove.NONE -> Unit
        }
    }

    // -- rule 4: the meeple close-up ----------------------------------------
    if (meepleFocus != null) {
        if (camera.preMeeple != null) return          // already zoomed in
        if (transformState.value.scale >= MEEPLE_ZOOM_TRIGGER) return
        camera.preMeeple = transformState.value
        animateTransform(
            transformState,
            BoardTransform.centeredOn(
                meepleFocus, MEEPLE_ZOOM_TARGET, viewW, viewH, insetTop, insetBottom,
            ),
            durationMs = 220,
        )
    } else {
        val back = camera.preMeeple ?: return
        camera.preMeeple = null
        // Not if the player took over during the sub-phase — they zoomed in to look
        // at something and pulling the rug is the rudest thing the camera can do.
        if (!camera.userAdjusted) animateTransform(transformState, back, durationMs = 220)
    }
}

/** The "fit board" button, and the double-tap zoom-out: back to the whole board. */
private suspend fun fitNow(
    state: GameState?,
    transformState: MutableState<BoardTransform>,
    camera: CameraPolicy,
    viewW: Float,
    viewH: Float,
    insetTop: Float,
    insetBottom: Float,
) {
    val bounds = state?.boundsWithMargin()?.atLeast(7) ?: return
    if (viewW <= 0f || viewH <= 0f) return
    camera.preMeeple = null
    camera.userAdjusted = false
    animateTransform(
        transformState,
        BoardTransform.fit(bounds, viewW, viewH, insetTop, insetBottom),
    )
}

/**
 * Double-tap: toggle between the whole-board fit and a close-up anchored on the
 * tapped point.
 *
 * Only reachable from a tap that hit nothing interactive (see [BoardCanvas]) —
 * tapping the same legal cell twice already means "next rotation", and a Compose
 * `onDoubleTap` would have put every single tap behind a ~300 ms timeout to
 * disambiguate. Immediate cell selection is worth more than a universal gesture.
 */
private suspend fun toggleZoom(
    state: GameState?,
    transformState: MutableState<BoardTransform>,
    camera: CameraPolicy,
    sx: Float,
    sy: Float,
    viewW: Float,
    viewH: Float,
    insetTop: Float,
    insetBottom: Float,
) {
    val bounds = state?.boundsWithMargin()?.atLeast(7) ?: return
    if (viewW <= 0f || viewH <= 0f) return
    val fitted = BoardTransform.fit(bounds, viewW, viewH, insetTop, insetBottom)
    val cur = transformState.value
    if (cur.scale > fitted.scale * 1.35f) {
        fitNow(state, transformState, camera, viewW, viewH, insetTop, insetBottom)
        return
    }
    val target = (fitted.scale * DOUBLE_TAP_FACTOR).coerceIn(MIN_SCALE, MAX_SCALE)
    camera.userAdjusted = true
    camera.preMeeple = null
    animateTransform(transformState, cur.gesture(sx, sy, 0f, 0f, zoom = target / cur.scale))
}

// --------------------------------------------------------------------------- //
// HUD                                                                          //
// --------------------------------------------------------------------------- //

@Composable
private fun GameHud(
    ui: GameUiState,
    state: GameState,
    assets: TileAssets?,
    landscape: Boolean,
    onFit: () -> Unit,
    onOpenBag: () -> Unit,
) {
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
                .padding(horizontal = 8.dp, vertical = if (landscape) 3.dp else 8.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(5.dp),
        ) {
            ScoreChip("You", state.humanScore, state.humanMeeples, CarcColors.Human)
            // A weakened preset names itself "Champion(weakened k4x172)", which a
            // 14-char chip renders as "Champion(weake". The chip drops the
            // parenthetical; the full name (and the budget note) stay in the status
            // bar and the end-of-game dialog, where the warning belongs.
            ScoreChip(
                MoveText.shortOpponent(state.opponentName).take(14),
                state.aiScore, state.aiMeeples, CarcColors.Ai,
            )
            Spacer(Modifier.weight(1f))
            // In the HUD rather than floating over the canvas, because the Scaffold
            // already reserves the top bar's height — a button anywhere on the board
            // occludes it, and at the right edge it sat squarely on a legal cell.
            // The ownership overlay used to have a toggle here. It is now always on
            // (a claim you have to ask to see is a claim you forget to ask about),
            // which also buys the HUD row back ~39dp on a 360dp-wide portrait phone.
            GlyphButton(onClick = onOpenBag, active = false) { bagGlyph(it) }
            FitBoardButton(onFit)
            Column(horizontalAlignment = Alignment.End) {
                Text(
                    tilesLeftLabel(state.tilesLeft),
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
                NextTileThumb(state, ui.ghost?.rotation ?: 0, assets, landscape)
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
private fun NextTileThumb(
    state: GameState,
    rotation: Int,
    assets: TileAssets,
    landscape: Boolean,
) {
    val bmp = assets.tile(state.nextTile?.image) ?: return
    Canvas(Modifier.size(if (landscape) 34.dp else 44.dp)) {
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

/**
 * Re-fit the board — the in-game recovery the round-2 build had no equivalent of
 * (no fit control, and double-tap did nothing).
 *
 * A drawn glyph rather than a font character or a Material icon: the icon set
 * shipped with the app does not carry a "fit to bounds" mark, and a Unicode
 * box-corner glyph renders as tofu on a device without it.
 */
@Composable
private fun FitBoardButton(onClick: () -> Unit, modifier: Modifier = Modifier) {
    GlyphButton(onClick = onClick, active = false, modifier = modifier) { fitGlyph(it) }
}

/**
 * A HUD button carrying a drawn glyph, optionally in an "on" state.
 *
 * Same reason as [FitBoardButton] for drawing rather than using an icon font: the
 * shipped Material set has no layers/bag mark, and a Unicode glyph renders as tofu
 * on a device without it. [active] swaps the container to the primary colour so the
 * ownership toggle reads as a switch rather than as an action.
 */
@Composable
private fun GlyphButton(
    onClick: () -> Unit,
    active: Boolean,
    modifier: Modifier = Modifier,
    glyph: DrawScope.(Color) -> Unit,
) {
    val container =
        if (active) MaterialTheme.colorScheme.primary
        else MaterialTheme.colorScheme.secondaryContainer
    val tint =
        if (active) MaterialTheme.colorScheme.onPrimary
        else MaterialTheme.colorScheme.onSecondaryContainer
    // A plain clickable box, NOT a SmallFloatingActionButton: the FAB carries a 40dp
    // minimum plus elevation padding, and three of them alongside the two score chips
    // overflowed a 360dp-wide portrait HUD — which pushed the tile-in-hand thumbnail
    // clean off the screen. 34dp is still above the 32dp comfortable-target floor for
    // a control sitting in a toolbar, and buys back the ~20dp the row needed.
    Box(
        modifier
            .size(HUD_BUTTON)
            .clip(RoundedCornerShape(10.dp))
            .background(container)
            .clickable(onClick = onClick),
        contentAlignment = Alignment.Center,
    ) {
        Canvas(Modifier.size(19.dp)) { glyph(tint) }
    }
}

/** Every HUD control is this size, so the row's width is predictable. */
private val HUD_BUTTON = 34.dp

/** A drawstring pouch — the tile bag. */
private fun DrawScope.bagGlyph(colour: Color) {
    val s = size.minDimension
    val w = s * 0.10f
    // Body: a rounded sack occupying the lower two thirds.
    drawRoundRect(
        color = colour,
        topLeft = Offset(s * 0.18f, s * 0.38f),
        size = Size(s * 0.64f, s * 0.50f),
        cornerRadius = androidx.compose.ui.geometry.CornerRadius(s * 0.16f),
        style = Stroke(width = w),
    )
    // Neck: two strokes pinching in to the tie.
    drawLine(
        colour, Offset(s * 0.32f, s * 0.38f), Offset(s * 0.40f, s * 0.18f),
        w, StrokeCap.Round,
    )
    drawLine(
        colour, Offset(s * 0.68f, s * 0.38f), Offset(s * 0.60f, s * 0.18f),
        w, StrokeCap.Round,
    )
    drawLine(
        colour, Offset(s * 0.36f, s * 0.22f), Offset(s * 0.64f, s * 0.22f),
        w, StrokeCap.Round,
    )
}

/** Four corner brackets around a centre dot — the universal "frame it" mark. */
private fun DrawScope.fitGlyph(colour: Color) {
    val s = size.minDimension
    val w = s * 0.11f
    val arm = s * 0.30f
    val lo = w / 2f                 // inset so the round caps are not clipped
    val hi = s - lo
    fun line(x1: Float, y1: Float, x2: Float, y2: Float) =
        drawLine(colour, Offset(x1, y1), Offset(x2, y2), w, StrokeCap.Round)
    line(lo, lo + arm, lo, lo); line(lo, lo, lo + arm, lo)
    line(hi - arm, lo, hi, lo); line(hi, lo, hi, lo + arm)
    line(hi, hi - arm, hi, hi); line(hi, hi, hi - arm, hi)
    line(lo + arm, hi, lo, hi); line(lo, hi, lo, hi - arm)
    drawCircle(colour, radius = s * 0.09f, center = Offset(s / 2f, s / 2f))
}

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

/**
 * What the last move materially did — "City completed — Champion +6, 1 meeple back".
 *
 * The gap this fills: the board shows a score CHANGED, never why, and Base+Farmers
 * pays in lumps big enough that an unexplained jump is the most confusing moment of a
 * game. It covers both seats — closing a city yourself is worth seeing too.
 *
 * A chip rather than a dialog, on purpose: it must never interrupt, and it must never
 * be the thing standing between the player and their next move. It stands until the
 * next move that scores replaces it, or until it is dismissed; a timeout was
 * considered and rejected, because the whole point is the player who looks up from
 * the board a few seconds later and asks "where did those points come from?".
 */
@Composable
private fun LastMoveChip(
    events: List<MoveEvent>,
    onDismiss: () -> Unit,
    modifier: Modifier,
) {
    Card(
        modifier.padding(horizontal = 12.dp, vertical = 6.dp),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.tertiaryContainer,
        ),
    ) {
        Row(
            Modifier.padding(start = 12.dp, top = 6.dp, bottom = 6.dp, end = 4.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(Modifier.weight(1f)) {
                for (e in events) {
                    Text(
                        e.text,
                        fontSize = 12.sp,
                        fontWeight = FontWeight.Medium,
                        color = MaterialTheme.colorScheme.onTertiaryContainer,
                    )
                }
            }
            Text(
                "✗",
                Modifier
                    .clip(RoundedCornerShape(8.dp))
                    .clickable(onClick = onDismiss)
                    .padding(horizontal = 10.dp, vertical = 4.dp),
                fontSize = 14.sp,
                color = MaterialTheme.colorScheme.onTertiaryContainer,
            )
        }
    }
}

@Composable
private fun ThinkingBanner(ui: GameUiState, state: GameState, modifier: Modifier) {
    val p = ui.progress
    Card(modifier.padding(12.dp).fillMaxWidth()) {
        Column(Modifier.padding(12.dp)) {
            val elapsed = p?.elapsedS?.toInt() ?: 0
            // The ETA is a rolling mean of this session's last few moves OF THE SAME
            // KIND, so it is only shown once there is one — never a guess from the
            // preset, and never a meeple-decision mean during a tile search.
            val eta = ui.etaSeconds?.let { " of ~${formatSeconds(it)}" } ?: ""
            Text(
                "${MoveText.shortOpponent(state.opponentName)} is thinking… ${elapsed}s$eta",
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
                    when (p?.phase) {
                        "exact" -> "solving the endgame exactly"
                        // Heuristic, not determinate: the tie-arbiter has no leaf
                        // count to show a fraction against, just a label hint that
                        // the champion is thinking longer than usual on a tie.
                        "arbiter" -> "arbitrating tied tile…"
                        else -> "searching"
                    },
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

/**
 * The floating action row.
 *
 * The two phases now share one grammar — **aim, then confirm**. The tile phase always
 * worked that way (tap a cell, ⟳ to rotate, ✓ to place); the meeple phase used to
 * commit on the first tap on a slot, which on targets a quarter-tile apart made every
 * mis-tap permanent. So the meeple phase gets the same ✗/✓ pair, and both phases get
 * a way back: ✗ un-aims, and ↶ takes the whole tile back (see
 * [GameViewModel.undoTilePlacement]).
 */
@Composable
private fun ActionButtons(ui: GameUiState, state: GameState, vm: GameViewModel) {
    if (!ui.canInteract) return
    val ghost = ui.ghost
    val slot = ui.selectedSlot
    val showTileFabs = state.isTilePhase && ghost != null
    if (!showTileFabs && !state.isMeeplePhase) return

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
        } else if (state.isMeeplePhase) {
            // Always available in this sub-phase: the tile is down but nothing else
            // has happened yet, which is the exact window in which taking it back is
            // free of consequence for the opponent's determinism.
            FloatingActionButton(
                onClick = vm::undoTilePlacement,
                containerColor = MaterialTheme.colorScheme.secondaryContainer,
            ) {
                Text("↶ Tile", Modifier.padding(horizontal = 10.dp), fontSize = 14.sp)
            }
            if (slot != null) {
                FloatingActionButton(onClick = vm::cancelMeeple) { Text("✗", fontSize = 22.sp) }
                FloatingActionButton(
                    onClick = vm::confirmMeeple,
                    containerColor = MaterialTheme.colorScheme.primary,
                ) { Text("✓", fontSize = 22.sp) }
            } else if (state.legal.meeplePassId != null) {
                // Rendered but inert for GameViewModel.PHASE_LOCK_MS — see
                // GameUiState.phaseLock. Hiding it instead would make the row jump.
                FloatingActionButton(onClick = vm::skipMeeple) {
                    Text("Skip meeple", Modifier.padding(horizontal = 12.dp), fontSize = 14.sp)
                }
            }
        }
    }
}

@Composable
private fun StatusBar(ui: GameUiState, state: GameState, landscape: Boolean) {
    // `ui.ghost` has a custom getter, so it is read into a local before use
    // (no smart cast on a property getter).
    val ghost = ui.ghost
    val opponent = MoveText.shortOpponent(state.opponentName)
    val text = when {
        state.isTerminated -> state.result?.verdict ?: "Game over."
        ui.aiFailed -> "$opponent's move failed — retry, or press Back to leave."
        ui.thinking -> "$opponent is thinking…"
        ui.busy -> "…"
        !state.isHumanTurn -> "$opponent's turn"
        state.isTilePhase && ghost != null ->
            MoveText.tilePhaseHint(ghost.index, ghost.rotationCount)
        state.isTilePhase -> "Your move — tap a highlighted square to place the tile"
        state.isMeeplePhase && ui.selectedSlot != null ->
            "✓ to place the meeple, ✗ to pick another"
        state.isMeeplePhase -> "Tap a spot for your meeple, skip, or ↶ take the tile back"
        else -> ""
    }
    val last = state.aiLastMove
    val lastLine = last?.let {
        MoveText.lastMoveLine(state.opponentName, it.describe, it.elapsedS)
    }
    Surface(
        Modifier.fillMaxWidth(),
        tonalElevation = 3.dp,
    ) {
        // Landscape has ~40% of the vertical room and the same three lines to
        // print, so they share a row instead of stacking.
        if (landscape) {
            Row(
                Modifier.padding(horizontal = 12.dp, vertical = 3.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                Text(text, Modifier.weight(1f), fontSize = 12.sp, fontWeight = FontWeight.Medium)
                lastLine?.let { Text(it, fontSize = 10.sp, maxLines = 1) }
                state.budgetNote?.let {
                    Text(it, fontSize = 9.sp, maxLines = 1, color = MaterialTheme.colorScheme.error)
                }
            }
        } else {
            Column(Modifier.padding(horizontal = 12.dp, vertical = 6.dp)) {
                Text(text, fontSize = 13.sp, fontWeight = FontWeight.Medium)
                lastLine?.let { Text(it, fontSize = 10.sp) }
                state.budgetNote?.let {
                    Text(it, fontSize = 10.sp, color = MaterialTheme.colorScheme.error)
                }
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
    val themLabel = MoveText.shortOpponent(opponentName)
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
                result.breakdown?.let { rows ->
                    Spacer(Modifier.height(8.dp))
                    ScoreBreakdown(rows, humanPlayer, themLabel)
                }
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

/**
 * What is still in the bag, per face.
 *
 * **Public information only.** The counts come from `get_bag()`, which derives them
 * as `full distribution - on the board - in hand`; the deck itself is never read,
 * because a shuffled deck's *order* is the future draw sequence. So this is exactly
 * the knowledge the fair champion's determinizations work from — a memory aid, not
 * an oracle.
 *
 * Faces with none left are greyed rather than removed, so the grid stays in one
 * order all game and "there are no more of these" is itself readable.
 */
@Composable
private fun BagDialog(bag: BagInfo?, assets: TileAssets?, onClose: () -> Unit) {
    AlertDialog(
        onDismissRequest = onClose,
        title = {
            Text(
                if (bag == null) "Tiles left"
                else "Tiles left — ${bag.totalRemaining}",
                fontSize = 18.sp,
            )
        },
        text = {
            if (bag == null) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    CircularProgressIndicator(Modifier.size(18.dp), strokeWidth = 2.dp)
                    Spacer(Modifier.width(10.dp))
                    Text("Counting the bag…", fontSize = 13.sp)
                }
            } else {
                Column {
                    Text(
                        "Unseen tiles — not on the board and not the one in hand. " +
                            "Public information; the deck order is never read.",
                        fontSize = 11.sp,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    Spacer(Modifier.height(8.dp))
                    LazyVerticalGrid(
                        columns = GridCells.Adaptive(minSize = 62.dp),
                        modifier = Modifier.heightIn(max = 420.dp),
                        horizontalArrangement = Arrangement.spacedBy(6.dp),
                        verticalArrangement = Arrangement.spacedBy(6.dp),
                    ) {
                        items(bag.faces.size) { i ->
                            BagFaceCell(bag.faces[i], assets)
                        }
                    }
                }
            }
        },
        confirmButton = { TextButton(onClick = onClose) { Text("Close") } },
    )
}

@Composable
private fun BagFaceCell(face: BagFace, assets: TileAssets?) {
    val gone = face.remaining == 0
    Column(horizontalAlignment = Alignment.CenterHorizontally) {
        val bmp = assets?.tile(face.image)
        Box(
            Modifier
                .size(52.dp)
                .clip(RoundedCornerShape(4.dp))
                .background(MaterialTheme.colorScheme.surfaceVariant),
            contentAlignment = Alignment.Center,
        ) {
            if (bmp != null) {
                Canvas(Modifier.size(52.dp)) {
                    drawImage(
                        image = bmp,
                        dstOffset = IntOffset.Zero,
                        dstSize = IntSize(size.width.roundToInt(), size.height.roundToInt()),
                        // Exhausted faces stay in place but recede.
                        alpha = if (gone) 0.22f else 1f,
                    )
                }
            }
        }
        Text(
            "×${face.remaining}",
            fontSize = 11.sp,
            fontWeight = if (gone) FontWeight.Normal else FontWeight.Bold,
            color = if (gone) MaterialTheme.colorScheme.onSurfaceVariant
            else MaterialTheme.colorScheme.onSurface,
            maxLines = 1,
            softWrap = false,
        )
    }
}

/**
 * Where the end-of-game jump came from.
 *
 * Base + Farmers scores most of its points in one lump at the last tile — farms
 * pay out, and every unfinished city/road/monastery pays a reduced rate — so the
 * scoreboard can go 11–56 to 15–106 in a single step with nothing on screen to
 * explain it. This is that step, itemised.
 */
@Composable
internal fun ScoreBreakdown(rows: List<ScoreBreakdownRow>, humanPlayer: Int, themLabel: String) {
    val you = rows.getOrNull(humanPlayer)
    val them = rows.getOrNull(1 - humanPlayer)
    if (you == null || them == null) return
    @Composable
    fun line(label: String, a: Int, b: Int, bold: Boolean = false) {
        Row(Modifier.fillMaxWidth()) {
            Text(
                label, Modifier.weight(1f), fontSize = 12.sp,
                fontWeight = if (bold) FontWeight.Bold else FontWeight.Normal,
            )
            Text(
                "$a", Modifier.width(BREAKDOWN_COL), fontSize = 12.sp,
                fontWeight = if (bold) FontWeight.Bold else FontWeight.Normal,
                textAlign = TextAlign.End, maxLines = 1, softWrap = false,
            )
            Text(
                "$b", Modifier.width(BREAKDOWN_COL), fontSize = 12.sp,
                fontWeight = if (bold) FontWeight.Bold else FontWeight.Normal,
                textAlign = TextAlign.End, maxLines = 1, softWrap = false,
            )
        }
    }
    Text("How it finished", fontSize = 12.sp, fontWeight = FontWeight.Medium)
    Row(Modifier.fillMaxWidth()) {
        Text("", Modifier.weight(1f), fontSize = 11.sp)
        // maxLines/softWrap, not `take(8)`: the column is a fixed width and
        // "Champion" is exactly the length that wrapped mid-word ("Champi/on").
        // Clipping to one line is the honest failure mode for a name that is
        // genuinely too long; the full name is printed under the table anyway.
        Text(
            "You", Modifier.width(BREAKDOWN_COL), fontSize = 11.sp,
            textAlign = TextAlign.End, maxLines = 1, softWrap = false,
            overflow = TextOverflow.Clip,
        )
        Text(
            themLabel, Modifier.width(BREAKDOWN_COL), fontSize = 11.sp,
            textAlign = TextAlign.End, maxLines = 1, softWrap = false,
            overflow = TextOverflow.Clip,
        )
    }
    line("Scored during play", you.duringPlay, them.duringPlay)
    line("Unfinished features", you.incomplete, them.incomplete)
    line("Farms", you.farms, them.farms)
    line("Total", you.total, them.total, bold = true)
}

/** Wide enough for "Champion" at 11.sp; the old 44.dp wrapped it mid-word. */
private val BREAKDOWN_COL = 62.dp
