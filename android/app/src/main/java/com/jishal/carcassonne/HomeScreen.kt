package com.jishal.carcassonne

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
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
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import kotlin.random.Random

private const val SEED_MAX = 1_000_000

/**
 * Entry screen: start a game, resume the autosave, or drop into the M0 debug
 * console. The difficulty control itself is M3 — for now the opponent is fixed
 * at the full champion budget and this screen only *reports* it.
 */
@Composable
fun HomeScreen(
    vm: GameViewModel,
    onPlay: () -> Unit,
    onDebug: () -> Unit,
) {
    val ui by vm.ui.collectAsStateWithLifecycle()
    var seat by rememberSaveable { mutableStateOf(Seat.HUMAN_FIRST) }
    var seedText by rememberSaveable { mutableStateOf(Random.nextInt(1, SEED_MAX).toString()) }

    // Warms the (slow) Python import and reads the YAML budget + save slot, so
    // the first new_game is not also paying for `import numpy`.
    LaunchedEffect(Unit) { vm.warmUpAndRefresh() }

    Column(
        Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        Text("Carcassonne", style = MaterialTheme.typography.headlineMedium)
        Text(
            "2-player Base + Farmers, against the production champion, on-device.",
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
                            selected = seat == option,
                            onClick = { seat = option },
                            label = { Text(option.label, fontSize = 12.sp) },
                        )
                    }
                }

                Row(verticalAlignment = Alignment.CenterVertically) {
                    OutlinedTextField(
                        value = seedText,
                        onValueChange = { new -> seedText = new.filter(Char::isDigit).take(9) },
                        label = { Text("Deck seed") },
                        singleLine = true,
                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                        modifier = Modifier.weight(1f),
                    )
                    Spacer(Modifier.width(8.dp))
                    OutlinedButton(onClick = {
                        seedText = Random.nextInt(1, SEED_MAX).toString()
                    }) { Text("Random") }
                }

                val budget = ui.budget
                Text(
                    if (budget != null) {
                        "Opponent: ${budget.championId} — k${budget.kDets}×${budget.simsPerDet} " +
                            "= ${budget.totalSims} sims/move (full champion budget)"
                    } else if (ui.warmingUp) {
                        "Opponent: champion — reading the production budget…"
                    } else {
                        "Opponent: champion (full production budget)"
                    },
                    fontSize = 11.sp,
                )
                Text(
                    "Full champion budget — moves may take ~10s. " +
                        "A difficulty slider arrives in the next milestone.",
                    fontSize = 11.sp,
                    color = MaterialTheme.colorScheme.primary,
                )

                Button(
                    onClick = {
                        val seed = seedText.toIntOrNull()?.takeIf { it > 0 }
                            ?: Random.nextInt(1, SEED_MAX)
                        vm.newGame(seat, seed)
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

        Spacer(Modifier.height(4.dp))
        TextButton(onClick = onDebug) { Text("Debug console", fontSize = 12.sp) }

        ui.error?.let {
            Text(
                it.toString(),
                color = MaterialTheme.colorScheme.error,
                fontSize = 11.sp,
            )
        }
    }
}
