package com.jishal.carcassonne

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle

/**
 * One line naming the opponent the *current preset* will produce.
 *
 * The champion stop has no client-side numbers by design (the YAML owns them),
 * so it prints what `production_budget()` read back — and says it is still
 * reading rather than inventing a figure.
 */
internal fun homeOpponentLine(ui: GameUiState): String {
    // ⛔ THE OPPONENT AXIS COMES FIRST (2026-09-02 text audit). Every line below
    // describes the on-device CHAMPION, and with "Remote Carcasum" selected the
    // Difficulty preset does not decide the opponent at all — its sims/k_dets are
    // simply not used, so printing them named an agent that was not going to play.
    if (ui.opponentMode == OpponentMode.REMOTE_CARCASUM) {
        return "Opponent: Carcasum on ${ui.remoteUrl} — the Difficulty setting " +
            "below does not apply; no search runs on this phone."
    }
    val d = ui.difficulty
    if (d.isTier1) return "Opponent: Tier-1 rule-based player — no search."
    val b = ui.budget
    val id = b?.championId ?: "champion"
    return when {
        d.totalSims != null ->
            "Opponent: $id at k${d.kDets}×${d.sims} = ${d.totalSims} sims/move."
        b != null ->
            "Opponent: $id — k${b.kDets}×${b.simsPerDet} = ${b.totalSims} sims/move."
        ui.warmingUp -> "Opponent: champion — reading this device's budget…"
        // "this device's", not "full production": since 2026-08-25 the mobile
        // deploy profile is not the same number as the champion of record's own
        // budget, and `production_budget()` reports the former.
        else -> "Opponent: champion (this device's full budget)."
    }
}

/**
 * Entry screen: start a game, resume the autosave, change difficulty, or drop
 * into the M0 debug console.
 *
 * The difficulty *chip* here is a read-out plus a shortcut — the setting itself
 * is owned by [SettingsScreen] and persisted in DataStore, so there is exactly
 * one place it can be changed.
 */
@Composable
fun HomeScreen(
    vm: GameViewModel,
    onPlay: () -> Unit,
    onSettings: () -> Unit,
    onDebug: () -> Unit,
    onPastGames: () -> Unit,
) {
    val ui by vm.ui.collectAsStateWithLifecycle()
    // Seat and seed live in the ViewModel, not in a `rememberSaveable` here: this
    // screen leaves the composition on every navigation, which re-rolled the seed.
    val form by vm.newGameForm.collectAsStateWithLifecycle()

    // Warms the (slow) Python import and reads the YAML budget + save slot, so
    // the first new_game is not also paying for `import numpy`.
    LaunchedEffect(Unit) { vm.warmUpAndRefresh() }

    Column(
        Modifier
            .fillMaxSize()
            // The status-bar clock used to sit on the title and the gesture pill
            // clipped the error banner at the bottom of the scroll.
            .safeDrawingPadding()
            .verticalScroll(rememberScrollState())
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        Text("Carcassonne", style = MaterialTheme.typography.headlineMedium)
        Text(
            if (ui.opponentMode == OpponentMode.REMOTE_CARCASUM) {
                "2-player Base + Farmers, against Carcasum over the tailnet."
            } else {
                "2-player Base + Farmers, against the production champion, on-device."
            },
            style = MaterialTheme.typography.bodySmall,
        )

        // ---- New game ------------------------------------------------------
        Card(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                Text("New game", fontWeight = FontWeight.Bold)

                Text("Who moves first", fontSize = 12.sp)
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    for (option in Seat.entries) {
                        FilterChip(
                            selected = form.seat == option,
                            onClick = { vm.setSeat(option) },
                            label = { Text(option.label, fontSize = 12.sp) },
                        )
                    }
                }

                Row(verticalAlignment = Alignment.CenterVertically) {
                    OutlinedTextField(
                        value = form.seedText,
                        onValueChange = vm::setSeedText,
                        label = { Text("Deck seed") },
                        singleLine = true,
                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                        modifier = Modifier.weight(1f),
                    )
                    Spacer(Modifier.width(8.dp))
                    OutlinedButton(onClick = vm::rerollSeed) { Text("Random") }
                }

                Text("Difficulty", fontSize = 12.sp)
                AssistChip(
                    onClick = onSettings,
                    label = {
                        Text(
                            "${ui.difficulty.label} — ${ui.difficulty.searchLabel}",
                            fontSize = 12.sp,
                        )
                    },
                    trailingIcon = { Text("›", fontSize = 16.sp) },
                )
                Text(homeOpponentLine(ui), fontSize = 11.sp)
                if (ui.opponentMode == OpponentMode.REMOTE_CARCASUM) {
                    // None of the three champion-budget lines below say anything
                    // true about a remote game; the one thing worth saying is the
                    // archive rule.
                    Text(
                        "Archived separately from the champion record.",
                        fontSize = 11.sp,
                        color = MaterialTheme.colorScheme.secondary,
                    )
                } else if (ui.difficulty.belowChampionBudget) {
                    Text(
                        "BELOW CHAMPION BUDGET — a weakened champion. Beating it is " +
                            "not beating the champion.",
                        fontSize = 11.sp,
                        color = MaterialTheme.colorScheme.error,
                    )
                } else if (ui.difficulty.isTier1) {
                    Text(
                        "A different agent (Tier-1 rule-based), not a weakened champion.",
                        fontSize = 11.sp,
                        color = MaterialTheme.colorScheme.secondary,
                    )
                } else {
                    Text(
                        // No seconds: the app has not measured this device yet, and
                        // the old "~10s" was a Python-era guess two engine changes
                        // ago. The thinking banner shows a real rolling mean once
                        // the opponent has actually moved.
                        "Full budget for this device — a move takes as long as it " +
                            "takes; the game screen shows a running estimate.",
                        fontSize = 11.sp,
                        color = MaterialTheme.colorScheme.primary,
                    )
                }

                Button(
                    onClick = {
                        vm.newGame(form.seat, resolveSeed(form.seedText))
                        onPlay()
                    },
                    enabled = !ui.busy && !ui.thinking,
                    modifier = Modifier.fillMaxWidth(),
                ) { Text("Start game") }
            }
        }

        // ---- Resume --------------------------------------------------------
        Card(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("Resume", fontWeight = FontWeight.Bold)
                Text(
                    if (ui.hasSave) {
                        "Picks up the autosave. The game is stored as (deck seed + move " +
                            "list) and replayed exactly, champion seeds included."
                    } else {
                        "No saved game."
                    },
                    fontSize = 11.sp,
                )
                Button(
                    onClick = { vm.resume(); onPlay() },
                    enabled = ui.hasSave && !ui.busy && !ui.thinking,
                    modifier = Modifier.fillMaxWidth(),
                ) { Text("Resume game") }
            }
        }

        // ---- Past games ----------------------------------------------------
        Card(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("Past games", fontWeight = FontWeight.Bold)
                Text(
                    if (ui.archiveCount > 0) {
                        "${ui.archiveCount} finished game" +
                            "${if (ui.archiveCount == 1) "" else "s"} archived — final " +
                            "scores, plus the deck seed and move list that reproduce " +
                            "each one exactly."
                    } else {
                        "Nothing yet. Games you play to the end are kept here."
                    },
                    fontSize = 11.sp,
                )
                OutlinedButton(
                    onClick = onPastGames,
                    enabled = ui.archiveCount > 0,
                    modifier = Modifier.fillMaxWidth(),
                ) { Text("View past games") }
            }
        }

        Spacer(Modifier.height(4.dp))
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            TextButton(onClick = onSettings) { Text("Settings", fontSize = 12.sp) }
            TextButton(onClick = onDebug) { Text("Debug console", fontSize = 12.sp) }
        }

        ui.error?.let {
            Text(
                it.toString(),
                color = MaterialTheme.colorScheme.error,
                fontSize = 11.sp,
            )
        }
    }
}
