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
import androidx.compose.foundation.clickable
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Slider
import androidx.compose.material3.SliderDefaults
import androidx.compose.material3.Switch
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

        OpponentCard(
            selected = ui.opponentMode,
            url = ui.remoteUrl,
            onSelect = vm::setOpponentMode,
            onUrl = vm::setRemoteUrl,
        )

        PlayAidsCard(
            previewNextTile = ui.previewNextTile,
            backgroundThinking = ui.backgroundThinking,
            onPreviewNextTile = vm::setPreviewNextTile,
            onBackgroundThinking = vm::setBackgroundThinking,
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
            // ⚠️ NOT a per-move duration. See Difficulty's kdoc: the old "~8-15s"
            // family were the plan's Python-search guesses and survived both the
            // Rust flip and the mobile budget doubling. The honest number is the
            // measured rolling mean the thinking banner already shows in play.
            Text(
                "Search size: ${selected.searchLabel}. Time per move is measured " +
                    "in-game, not guessed here.",
                fontSize = 11.sp,
            )

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
            "(this device's profile in PRODUCTION.yaml)."
    else -> "This device's full budget from PRODUCTION.yaml (reading…)."
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
                    "this device's $full. This is a WEAKENED agent; beating it is " +
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
// Opponent                                                                     //
// --------------------------------------------------------------------------- //

/**
 * The two play aids added in the 2026-09-02 UI build.
 *
 * Both default ON, and both say plainly what they do — including the one thing a
 * player would reasonably want to know about the peek, which is that the app
 * RECORDS having shown it. That is not a privacy note; it is the honest version of
 * "this changes what you knew, and the game log says so".
 */
@Composable
private fun PlayAidsCard(
    previewNextTile: Boolean,
    backgroundThinking: Boolean,
    onPreviewNextTile: (Boolean) -> Unit,
    onBackgroundThinking: (Boolean) -> Unit,
) {
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("While the opponent thinks", fontWeight = FontWeight.Bold)

            ToggleRow(
                title = "Show your next tile",
                subtitle = "During the opponent's turn only, show the tile you are " +
                    "next in line to draw. It is a preview, not an early draw — the " +
                    "real draw still happens on your turn, and if the opponent's " +
                    "move leaves nowhere to put it you will draw a different one. " +
                    "Games where it was shown are stamped in the game record.",
                checked = previewNextTile,
                onChange = onPreviewNextTile,
            )
            HorizontalDivider()
            ToggleRow(
                title = "Keep thinking in the background",
                subtitle = "Show a notification while the opponent is deciding, so " +
                    "Android keeps giving the app full CPU when you switch away. " +
                    "Off is slower, never wrong: an interrupted turn is always " +
                    "re-played from the autosave when you come back.",
                checked = backgroundThinking,
                onChange = onBackgroundThinking,
            )
            Text(
                "The opponent's own drawn tile is always shown — it is face-up " +
                    "under the rules, and the opponent's search already knows it.",
                fontSize = 10.sp,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

@Composable
private fun ToggleRow(
    title: String,
    subtitle: String,
    checked: Boolean,
    onChange: (Boolean) -> Unit,
) {
    Row(
        Modifier.fillMaxWidth().clickable { onChange(!checked) },
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(Modifier.weight(1f).padding(end = 12.dp, top = 4.dp, bottom = 4.dp)) {
            Text(title, style = MaterialTheme.typography.titleSmall)
            Text(
                subtitle,
                fontSize = 11.sp,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        Switch(checked = checked, onCheckedChange = onChange)
    }
}

/**
 * WHO you play. Deliberately a two-button choice rather than another slider:
 * this is not a strength axis, it is a different opponent on a different
 * machine, and the archive is stamped differently for it.
 *
 * The warning line under "Remote Carcasum" is not decoration. The one way this
 * feature could damage the program is a Carcasum game being read later as a
 * champion game, so the screen says out loud what the archive will say.
 */
@Composable
private fun OpponentCard(
    selected: OpponentMode,
    url: String,
    onSelect: (OpponentMode) -> Unit,
    onUrl: (String) -> Unit,
) {
    var editing by remember { mutableStateOf(false) }
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("Opponent", fontWeight = FontWeight.Bold)
            Row(
                Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                for (m in OpponentMode.entries) {
                    TextButton(
                        onClick = { if (m != selected) onSelect(m) },
                        modifier = Modifier.weight(1f),
                    ) {
                        Text(
                            m.label,
                            fontSize = 12.sp,
                            fontWeight = if (m == selected) FontWeight.Bold else FontWeight.Normal,
                            color = if (m == selected) MaterialTheme.colorScheme.primary
                            else MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                }
            }
            Text(selected.label, style = MaterialTheme.typography.titleMedium)
            Text(selected.blurb, fontSize = 12.sp)

            if (selected == OpponentMode.REMOTE_CARCASUM) {
                // ⚠️ NO LITERAL LABEL HERE (2026-09-02 text audit). This used to
                // print "carcasum_remote_5000ms", which is simply wrong whenever
                // the daemon is launched in fixed-playout mode (`server.py
                // --playouts` labels itself `carcasum_remote_p<N>`). The exclusion
                // is what matters and it holds for every spelling — the archive
                // label always starts `carcasum_remote`, and `e4_archives.py`
                // counts only an exact "champion".
                Text(
                    "Games against Carcasum are archived under their own " +
                        "\"carcasum_remote…\" label and are NEVER counted in the " +
                        "champion record. The exact label, and the budget or " +
                        "playout count behind it, come from the server itself " +
                        "when the game starts.",
                    fontSize = 10.sp,
                    color = MaterialTheme.colorScheme.error,
                )
                Text(
                    "Server: $url",
                    fontSize = 11.sp,
                    fontFamily = FontFamily.Monospace,
                )
                TextButton(onClick = { editing = true }) { Text("Change server…") }
                Text(
                    "The laptop must be running scripts/carcasum_remote/server.py " +
                        "and both devices must be on the tailnet. The address is " +
                        "checked when the game starts, not when you type it.",
                    fontSize = 10.sp,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            } else {
                Text(
                    "A change applies to the NEXT game.",
                    fontSize = 10.sp,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }

    if (editing) {
        RemoteUrlDialog(
            initial = url,
            onDismiss = { editing = false },
            onConfirm = { onUrl(it); editing = false },
        )
    }
}

@Composable
private fun RemoteUrlDialog(
    initial: String,
    onDismiss: () -> Unit,
    onConfirm: (String) -> Unit,
) {
    var text by remember { mutableStateOf(initial) }
    val valid = OpponentMode.looksLikeUrl(text)
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Remote opponent server") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedTextField(
                    value = text,
                    onValueChange = { text = it },
                    singleLine = true,
                    label = { Text("http://host:port") },
                    isError = !valid,
                    modifier = Modifier.fillMaxWidth(),
                )
                Text(
                    "Default: ${OpponentMode.DEFAULT_URL} (the laptop's tailnet " +
                        "address). Plain HTTP with no auth — this is only safe " +
                        "because the tailnet is private.",
                    fontSize = 10.sp,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        },
        confirmButton = {
            TextButton(onClick = { onConfirm(text.trim()) }, enabled = valid) { Text("Save") }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Cancel") } },
    )
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
                    "2-player Base + Farmers. The champion runs entirely " +
                        "on-device; the optional Carcasum opponent runs on another " +
                        "machine over the tailnet and is archived separately.",
                    fontSize = 12.sp,
                )
                Text(
                    "Champion of record: ${budget?.championId ?: "(reading PRODUCTION.yaml…)"}",
                    fontSize = 12.sp,
                    fontFamily = FontFamily.Monospace,
                )
                budget?.let {
                    // ⚠️ "This device runs", not "Full budget" (2026-09-02 text
                    // audit). `production_budget()` reports what THIS PHONE
                    // searches — the `deploy_profiles.mobile` numbers — and since
                    // 2026-08-25 that is no longer the same as the champion of
                    // record's own budget. Calling it "full" quietly asserted they
                    // were equal.
                    Text(
                        "This device runs: k${it.kDets} × ${it.simsPerDet} = " +
                            "${it.totalSims} sims/move (the mobile profile in " +
                            "PRODUCTION.yaml).",
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
