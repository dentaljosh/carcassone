package com.jishal.carcassonne

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.rememberScrollState
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import android.content.res.Configuration

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
                    DebugScreen()
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

    Scaffold { insets ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(insets)
                .padding(horizontal = 12.dp),
            verticalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            Text(
                "Carcassonne bridge — M0 debug",
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
                OutlinedButton(onClick = vm::getState, enabled = !state.busy, modifier = Modifier.weight(1f)) {
                    Text("state", fontSize = 13.sp)
                }
                OutlinedButton(onClick = vm::getProgress, modifier = Modifier.weight(1f)) {
                    Text("progress", fontSize = 13.sp)
                }
                OutlinedButton(onClick = vm::saveGame, enabled = !state.busy, modifier = Modifier.weight(1f)) {
                    Text("save", fontSize = 13.sp)
                }
                OutlinedButton(onClick = vm::clear, modifier = Modifier.weight(1f)) {
                    Text("clear", fontSize = 13.sp)
                }
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
}

@Composable
private fun LogCard(line: LogLine) {
    val scroll = rememberScrollState()
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
            Text(
                line.body,
                fontFamily = FontFamily.Monospace,
                fontSize = 11.sp,
                softWrap = false,
                modifier = Modifier
                    .fillMaxWidth()
                    .horizontalScroll(scroll)
                    .padding(top = 4.dp),
                color = if (line.isError) MaterialTheme.colorScheme.onErrorContainer else Color.Unspecified,
            )
        }
    }
}
