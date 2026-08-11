package com.jishal.carcassonne

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.launch
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * Finished games, newest first.
 *
 * Every row is rendered from the archived JSON alone — **no replay**. The record
 * already carries the final scores, the verdict and the end-of-game breakdown, which
 * is exactly why `archive_record` stores that summary alongside the replayable
 * `(deck_seed, actions)` core: a list of 200 games must not cost 200 game replays to
 * draw. The seed and move list are still in the file for anyone who wants to replay
 * it on the desktop (see android/README.md).
 */
@Composable
fun PastGamesScreen(vm: GameViewModel, onBack: () -> Unit) {
    var games by remember { mutableStateOf<List<ArchivedGame>?>(null) }
    var showing by remember { mutableStateOf<ArchivedGame?>(null) }
    val scope = rememberCoroutineScope()

    LaunchedEffect(Unit) { games = vm.listArchivedGames() }

    Column(
        Modifier
            .fillMaxSize()
            .safeDrawingPadding()
            .padding(horizontal = 16.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            TextButton(onClick = onBack) { Text("← Home") }
            Spacer(Modifier.width(4.dp))
            Text("Past games", style = MaterialTheme.typography.titleMedium)
        }

        val list = games
        when {
            list == null -> Text("Loading…", fontSize = 13.sp, modifier = Modifier.padding(8.dp))
            list.isEmpty() -> Column(Modifier.padding(top = 12.dp)) {
                Text("No finished games yet.", fontWeight = FontWeight.Medium)
                Spacer(Modifier.height(6.dp))
                Text(
                    "Every game you play to the end is archived here — the final " +
                        "score plus the deck seed and move list that reproduce it " +
                        "exactly.",
                    fontSize = 12.sp,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            else -> LazyColumn(
                Modifier.fillMaxWidth(),
                verticalArrangement = Arrangement.spacedBy(8.dp),
                contentPadding = PaddingValues(vertical = 8.dp),
            ) {
                items(list.size) { i ->
                    PastGameRow(list[i]) { showing = list[i] }
                }
            }
        }
    }

    showing?.let { game ->
        PastGameDialog(
            game = game,
            onDelete = {
                scope.launch {
                    vm.deleteArchivedGame(game.fileName)
                    games = vm.listArchivedGames()
                    showing = null
                }
            },
            onClose = { showing = null },
        )
    }
}

/** One line: outcome, date, seat, opponent, score. */
@Composable
private fun PastGameRow(game: ArchivedGame, onClick: () -> Unit) {
    Card(Modifier.fillMaxWidth().clickable(onClick = onClick)) {
        Row(
            Modifier.padding(12.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            OutcomeBadge(game.outcome)
            Spacer(Modifier.width(12.dp))
            Column(Modifier.weight(1f)) {
                Text(
                    "${game.humanScore} – ${game.aiScore}",
                    fontWeight = FontWeight.Bold,
                    fontSize = 16.sp,
                )
                Text(
                    "${formatFinished(game.finishedAt)} · ${game.seatLabel} · " +
                        MoveText.shortOpponent(game.opponentName),
                    fontSize = 11.sp,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    maxLines = 1,
                )
            }
            Text("›", fontSize = 18.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

@Composable
private fun OutcomeBadge(outcome: String) {
    val colour = when (outcome) {
        "W" -> CarcColors.Human
        "L" -> CarcColors.Ai
        else -> MaterialTheme.colorScheme.onSurfaceVariant
    }
    Box(
        Modifier
            .size(34.dp)
            .clip(RoundedCornerShape(17.dp))
            .background(colour.copy(alpha = 0.18f)),
        contentAlignment = Alignment.Center,
    ) {
        Text(outcome, fontWeight = FontWeight.Bold, color = colour, fontSize = 15.sp)
    }
}

/**
 * The end-of-game summary again, rebuilt from the archived JSON.
 *
 * Same [ScoreBreakdown] composable the live result dialog uses — the archive stores
 * the identical `result` object, so there is one renderer and no chance of the two
 * drifting into disagreement about a finished game.
 */
@Composable
private fun PastGameDialog(game: ArchivedGame, onDelete: () -> Unit, onClose: () -> Unit) {
    val themLabel = MoveText.shortOpponent(game.opponentName)
    AlertDialog(
        onDismissRequest = onClose,
        title = { Text(game.result?.verdict ?: "Finished game") },
        text = {
            Column {
                Text("Final score  You ${game.humanScore} – ${game.aiScore} $themLabel")
                game.result?.let { r ->
                    Text(
                        if (r.diff == 0) "A dead heat."
                        else "Margin: ${r.diff} point${if (r.diff == 1) "" else "s"}",
                    )
                    r.breakdown?.let { rows ->
                        Spacer(Modifier.height(8.dp))
                        ScoreBreakdown(rows, game.humanPlayer, themLabel)
                    }
                }
                Spacer(Modifier.height(10.dp))
                Text("Opponent: ${game.opponentName}", fontSize = 12.sp)
                Text("Played: ${formatFinished(game.finishedAt)}", fontSize = 12.sp)
                Text("Tiles placed: ${game.tilesPlaced}", fontSize = 12.sp)
                Spacer(Modifier.height(8.dp))
                // The seed is the point of keeping the record at all — it is what
                // makes the game reproducible on the desktop.
                Text(
                    "Deck seed ${game.deckSeed} · replayable from this file",
                    fontSize = 11.sp,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                game.result?.budgetNote?.let {
                    Spacer(Modifier.height(8.dp))
                    Text(it, color = MaterialTheme.colorScheme.error, fontSize = 11.sp)
                }
            }
        },
        confirmButton = { TextButton(onClick = onClose) { Text("Close") } },
        dismissButton = {
            TextButton(onClick = onDelete) {
                Text("Delete", color = MaterialTheme.colorScheme.error)
            }
        },
    )
}

/** `finished_at` is bridge-side epoch SECONDS (python `time.time()`), not millis. */
private fun formatFinished(epochSeconds: Long): String {
    if (epochSeconds <= 0L) return "unknown date"
    return SimpleDateFormat("d MMM yyyy, HH:mm", Locale.getDefault())
        .format(Date(epochSeconds * 1000L))
}
