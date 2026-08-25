package com.jishal.carcassonne

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Slider
import androidx.compose.material3.SliderDefaults
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
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import org.json.JSONObject
import kotlin.math.roundToInt

/**
 * Difficulty, the resolved AI manifest, and About.
 *
 * The screen is deliberately honest about what each stop *is*: three of the five
 * are the champion with its search cut down (and say so, in the error colour),
 * one is a different agent entirely, and one is the real thing. The champion
 * stop never prints a hardcoded budget — it prints what `production_budget()`
 * read out of `governance/PRODUCTION.yaml`.
 */
@Composable
fun SettingsScreen(vm: GameViewModel, onBack: () -> Unit) {
    val ui by vm.ui.collectAsStateWithLifecycle()
    var showManifest by remember { mutableStateOf(false) }
    var showAbout by remember { mutableStateOf(false) }

    BackHandler { onBack() }

    // Settings is reachable before Home has finished warming up (and after a
    // process restart), so make sure the budget read-out is populated.
    LaunchedEffect(Unit) { if (ui.budget == null) vm.warmUpAndRefresh() }

    Column(
        Modifier
            .fillMaxSize()
            // Without this the "← Back" button was drawn UNDER the status bar and
            // was not merely ugly but untappable — the system window took the taps.
            .safeDrawingPadding()
            .verticalScroll(rememberScrollState())
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            TextButton(onClick = onBack) { Text("← Back") }
            Spacer(Modifier.weight(1f))
        }
        Text("Settings", style = MaterialTheme.typography.headlineSmall)

        DifficultyCard(
            selected = ui.difficulty,
            budget = ui.budget,
            onSelect = vm::setDifficulty,
        )

        TieArbLevelCard(
            selected = ui.tieArbLevel,
            onSelect = vm::setTieArbLevel,
        )

        Card(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(vertical = 4.dp)) {
                SettingsRow(
                    title = "AI manifest",
                    subtitle = "The resolved runtime config, hashes and leaf proof " +
                        "the champion was built from.",
                    onClick = { showManifest = true },
                )
                HorizontalDivider()
                SettingsRow(
                    title = "About",
                    subtitle = "Build, champion of record, credits.",
                    onClick = { showAbout = true },
                )
            }
        }
    }

    if (showManifest) ManifestDialog(onDismiss = { showManifest = false })
    if (showAbout) AboutDialog(budget = ui.budget, onDismiss = { showAbout = false })
}

// --------------------------------------------------------------------------- //
// Difficulty                                                                   //
// --------------------------------------------------------------------------- //

@Composable
private fun DifficultyCard(
    selected: Difficulty,
    budget: ProductionBudget?,
    onSelect: (Difficulty) -> Unit,
) {
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("Difficulty", fontWeight = FontWeight.Bold)

            val index = Difficulty.entries.indexOf(selected).toFloat()
            Slider(
                value = index,
                // Guarded: the slider emits on every drag tick, and each accepted
                // value is a DataStore write.
                onValueChange = { v ->
                    val d = Difficulty.fromIndex(v.roundToInt())
                    if (d != selected) onSelect(d)
                },
                valueRange = 0f..(Difficulty.entries.lastIndex).toFloat(),
                // 5 stops = 3 intermediate steps.
                steps = Difficulty.entries.size - 2,
                colors = SliderDefaults.colors(),
                modifier = Modifier.fillMaxWidth(),
            )
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                for (d in Difficulty.entries) {
                    Text(
                        d.label,
                        fontSize = 9.sp,
                        fontWeight = if (d == selected) FontWeight.Bold else FontWeight.Normal,
                        color = if (d == selected) MaterialTheme.colorScheme.primary
                        else MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }

            Spacer(Modifier.height(2.dp))
            Text(selected.label, style = MaterialTheme.typography.titleMedium)
            Text(selected.blurb, fontSize = 12.sp)
            Text(budgetLine(selected, budget), fontSize = 12.sp, fontWeight = FontWeight.Medium)
            Text("Estimated ${selected.estPerMove} per move on a phone.", fontSize = 11.sp)

            BudgetWarning(selected, budget)

            Text(
                "A difficulty change applies to the NEXT game. A game in progress " +
                    "keeps the budget it was started with (the save file records it).",
                fontSize = 10.sp,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

/**
 * The numbers for a stop. For [Difficulty.CHAMPION] there are no client-side
 * numbers to print at all — the budget comes back from the YAML via
 * `production_budget()`, and until that read lands we say so rather than guess.
 */
private fun budgetLine(d: Difficulty, budget: ProductionBudget?): String = when {
    d.isTier1 -> "Rule-based — no search budget."
    d.kDets != null && d.sims != null ->
        "k${d.kDets} × ${d.sims} = ${d.totalSims} sims/move."
    budget != null ->
        "k${budget.kDets} × ${budget.simsPerDet} = ${budget.totalSims} sims/move " +
            "(read from PRODUCTION.yaml)."
    else -> "The full budget from PRODUCTION.yaml (reading…)."
}

@Composable
private fun BudgetWarning(d: Difficulty, budget: ProductionBudget?) {
    when {
        d.isTier1 -> Card(
            Modifier.fillMaxWidth(),
            colors = CardDefaults.cardColors(
                containerColor = MaterialTheme.colorScheme.secondaryContainer,
            ),
        ) {
            Text(
                "DIFFERENT AGENT — this is the Tier-1 rule-based player, not a " +
                    "weakened champion. Beating it says nothing about the champion.",
                Modifier.padding(10.dp),
                fontSize = 11.sp,
                color = MaterialTheme.colorScheme.onSecondaryContainer,
            )
        }

        d.belowChampionBudget -> Card(
            Modifier.fillMaxWidth(),
            colors = CardDefaults.cardColors(
                containerColor = MaterialTheme.colorScheme.errorContainer,
            ),
        ) {
            val full = budget?.let { "k${it.kDets}×${it.simsPerDet}=${it.totalSims}" }
                ?: "its full YAML budget"
            Text(
                "BELOW CHAMPION BUDGET — running ${d.totalSims} sims/move against " +
                    "the champion's $full. This is a WEAKENED agent; beating it is " +
                    "not beating the champion.",
                Modifier.padding(10.dp),
                fontSize = 11.sp,
                color = MaterialTheme.colorScheme.onErrorContainer,
            )
        }

        else -> Text(
            "Full champion budget — a win here is a win against the champion of record.",
            fontSize = 11.sp,
            color = MaterialTheme.colorScheme.primary,
        )
    }
}

// --------------------------------------------------------------------------- //
// Tie-arbiter level                                                            //
// --------------------------------------------------------------------------- //

/**
 * How hard the mobile tie-arbiter searches when the champion's top moves are
 * tied at the leaf. A separate axis from [DifficultyCard]'s search budget —
 * this only spends extra time on the rare tied decision, not on every move.
 */
@Composable
private fun TieArbLevelCard(
    selected: TieArbLevel,
    onSelect: (TieArbLevel) -> Unit,
) {
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("Tie-break search", fontWeight = FontWeight.Bold)

            val index = TieArbLevel.entries.indexOf(selected).toFloat()
            Slider(
                value = index,
                // Guarded: the slider emits on every drag tick, and each accepted
                // value is a DataStore write.
                onValueChange = { v ->
                    val l = TieArbLevel.fromIndex(v.roundToInt())
                    if (l != selected) onSelect(l)
                },
                valueRange = 0f..(TieArbLevel.entries.lastIndex).toFloat(),
                // 4 stops = 2 intermediate steps.
                steps = TieArbLevel.entries.size - 2,
                colors = SliderDefaults.colors(),
                modifier = Modifier.fillMaxWidth(),
            )
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                for (l in TieArbLevel.entries) {
                    Text(
                        l.label,
                        fontSize = 9.sp,
                        fontWeight = if (l == selected) FontWeight.Bold else FontWeight.Normal,
                        color = if (l == selected) MaterialTheme.colorScheme.primary
                        else MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }

            Spacer(Modifier.height(2.dp))
            Text(selected.label, style = MaterialTheme.typography.titleMedium)
            Text(selected.perTileEstimate, fontSize = 12.sp)

            Text(
                "Only spent on tied tile decisions — not every move. A tie-break " +
                    "change applies to the NEXT game.",
                fontSize = 10.sp,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

// --------------------------------------------------------------------------- //
// Rows and dialogs                                                             //
// --------------------------------------------------------------------------- //

@Composable
private fun SettingsRow(title: String, subtitle: String, onClick: () -> Unit) {
    TextButton(onClick = onClick, modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.fillMaxWidth().padding(vertical = 4.dp)) {
            Text(title, fontWeight = FontWeight.Medium)
            Text(subtitle, fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

/**
 * Pretty-prints `get_manifest()`.
 *
 * With a game in progress this is the manifest of the agent actually playing;
 * with none it is the deterministic spec-derived manifest for the champion of
 * record (the bridge decides, and reports which in `source`).
 */
@Composable
private fun ManifestDialog(onDismiss: () -> Unit) {
    var text by remember { mutableStateOf<String?>(null) }

    // getManifest() already hops to the bridge thread; with no game in progress
    // it resolves the spec manifest (verify included), so it is not instant.
    LaunchedEffect(Unit) {
        text = runCatching { prettyManifest(PythonBridge.getManifest()) }
            .getOrElse { t -> "Could not read the manifest:\n${BridgeJson.errorOf(t)}" }
    }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("AI manifest") },
        text = {
            val body = text
            if (body == null) {
                Text("Resolving the champion manifest…", fontSize = 12.sp)
            } else {
                // Wrap, don't pan. The manifest is mostly long unbroken tokens —
                // absolute paths and hashes — and a horizontal scroll on a
                // dialog-width viewport just cut them off mid-character with no
                // affordance saying there was more. `heightIn` only caps: in
                // landscape the dialog's own max height wins and this still fits.
                Text(
                    body,
                    Modifier
                        .fillMaxWidth()
                        .heightIn(max = 420.dp)
                        .verticalScroll(rememberScrollState()),
                    fontFamily = FontFamily.Monospace,
                    fontSize = 10.sp,
                    softWrap = true,
                )
            }
        },
        confirmButton = { TextButton(onClick = onDismiss) { Text("Close") } },
    )
}

/**
 * Unwrap the bridge envelope and indent. The manifest itself is the payload; the
 * envelope's `ok`/`schema` fields are noise in a human-readable sheet.
 */
internal fun prettyManifest(raw: String): String {
    val o = JSONObject(raw)
    if (!o.optBoolean("ok", false)) {
        val e = o.optJSONObject("error")
        return "error: ${e?.optString("code")}\n${e?.optString("message")}"
    }
    val header = buildString {
        o.optString("manifest_source").takeIf { it.isNotEmpty() }
            ?.let { appendLine("source: $it") }
        o.optString("opponent_name").takeIf { it.isNotEmpty() }
            ?.let { appendLine("opponent: $it") }
        o.optString("production_yaml").takeIf { it.isNotEmpty() }
            ?.let { appendLine("yaml: $it") }
        if (!o.isNull("budget_note")) {
            o.optString("budget_note").takeIf { it.isNotEmpty() }?.let { appendLine(it) }
        }
    }
    val manifest = if (o.isNull("manifest")) null else o.optJSONObject("manifest")
    val body = manifest?.toString(2)
        ?: "(no manifest — the Tier-1 rule-based player has no search config)"
    return if (header.isEmpty()) body else "$header\n$body"
}

@Composable
private fun AboutDialog(budget: ProductionBudget?, onDismiss: () -> Unit) {
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("About") },
        text = {
            Column(
                Modifier
                    .fillMaxWidth()
                    .heightIn(max = 420.dp)
                    .verticalScroll(rememberScrollState()),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                Text("Carcassonne AI", fontWeight = FontWeight.Bold)
                Text(
                    "2-player Base + Farmers against the production champion, " +
                        "running entirely on-device.",
                    fontSize = 12.sp,
                )
                Text(
                    "Champion of record: ${budget?.championId ?: "(reading PRODUCTION.yaml…)"}",
                    fontSize = 12.sp,
                    fontFamily = FontFamily.Monospace,
                )
                budget?.let {
                    Text(
                        "Full budget: k${it.kDets} × ${it.simsPerDet} = ${it.totalSims} " +
                            "sims/move.",
                        fontSize = 12.sp,
                    )
                }
                HorizontalDivider()
                Text(
                    "Personal build — tile art © Hans im Glück, not for distribution.",
                    fontSize = 11.sp,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        },
        confirmButton = { TextButton(onClick = onDismiss) { Text("Close") } },
    )
}
