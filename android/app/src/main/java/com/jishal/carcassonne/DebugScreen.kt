package com.jishal.carcassonne

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel

/**
 * The M0 raw-JSON console. Superseded as the app's front door by [HomeScreen] /
 * [GameScreen], kept reachable from Home because it is the only place that shows
 * the bridge's exact responses and per-call wall-clock — which is what you want
 * the first time this runs on a real phone.
 */
@Composable
fun DebugScreen(vm: DebugViewModel = viewModel()) {
    val state by vm.state.collectAsStateWithLifecycle()
    val listState = rememberLazyListState()

    // Import the bridge module once, at first composition, so the (slow) first
    // import cost is not attributed to the first new_game.
    LaunchedEffect(Unit) { vm.warmUp() }

    LaunchedEffect(state.lines.size) {
        if (state.lines.isNotEmpty()) listState.animateScrollToItem(state.lines.lastIndex)
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(horizontal = 12.dp),
        verticalArrangement = Arrangement.spacedBy(6.dp),
    ) {
        Text(
            "Carcassonne bridge — debug console",
            style = MaterialTheme.typography.titleMedium,
            modifier = Modifier.padding(top = 8.dp),
        )

        Button(
            onClick = vm::newGameTiny,
            enabled = !state.busy,
            modifier = Modifier.fillMaxWidth(),
        ) { Text("New game (tiny: tier1, k1x16)") }

        Button(
            onClick = vm::newGameChampion,
            enabled = !state.busy,
            modifier = Modifier.fillMaxWidth(),
        ) { Text("New game (champion full budget)") }

        Button(
            onClick = vm::aiMove,
            enabled = !state.busy,
            modifier = Modifier.fillMaxWidth(),
        ) { Text("AI move") }

        Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            ConsoleButton("state", vm::getState, enabled = !state.busy, modifier = Modifier.weight(1f))
            ConsoleButton("progress", vm::getProgress, modifier = Modifier.weight(1f))
            ConsoleButton("save", vm::saveGame, enabled = !state.busy, modifier = Modifier.weight(1f))
            ConsoleButton("clear", vm::clear, modifier = Modifier.weight(1f))
        }

        if (state.busy) {
            LinearProgressIndicator(modifier = Modifier.fillMaxWidth())
            Text(
                "python thread busy — a full-budget move can take 10s+",
                style = MaterialTheme.typography.labelSmall,
            )
        }

        LazyColumn(
            state = listState,
            modifier = Modifier
                .fillMaxWidth()
                .weight(1f),
            verticalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            items(state.lines) { line -> LogCard(line) }
        }
    }
}

/**
 * One of the four equal-width console buttons.
 *
 * The label is a single unbreakable line: at the default OutlinedButton content
 * padding (24.dp a side) "progress" did not fit a quarter-width button and wrapped
 * mid-word to "progre/ss". Narrow padding buys the ~50dp the longest label needs.
 */
@Composable
private fun ConsoleButton(
    label: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
) {
    OutlinedButton(
        onClick = onClick,
        enabled = enabled,
        modifier = modifier,
        contentPadding = PaddingValues(horizontal = 6.dp, vertical = 8.dp),
    ) {
        Text(label, fontSize = 13.sp, maxLines = 1, softWrap = false)
    }
}

@Composable
private fun LogCard(line: LogLine) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = if (line.isError) {
            CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.errorContainer)
        } else {
            CardDefaults.cardColors()
        },
    ) {
        Column(Modifier.padding(8.dp)) {
            Row(
                Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(
                    line.label,
                    fontWeight = FontWeight.Bold,
                    fontSize = 13.sp,
                    color = if (line.isError) MaterialTheme.colorScheme.onErrorContainer else Color.Unspecified,
                )
                line.elapsedMs?.let {
                    Text("$it ms", fontFamily = FontFamily.Monospace, fontSize = 12.sp)
                }
            }
            // Wrap rather than pan: a per-row horizontal scroll inside a vertically
            // scrolling list is close to unusable on a phone, and the raw bridge JSON
            // is one long line, so everything past the card's width simply vanished.
            Text(
                line.body,
                fontFamily = FontFamily.Monospace,
                fontSize = 11.sp,
                softWrap = true,
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(top = 4.dp),
                color = if (line.isError) MaterialTheme.colorScheme.onErrorContainer else Color.Unspecified,
            )
        }
    }
}
