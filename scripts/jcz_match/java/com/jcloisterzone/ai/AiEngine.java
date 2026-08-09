package com.jcloisterzone.ai;

import com.google.gson.Gson;
import com.jcloisterzone.Player;
import com.jcloisterzone.ai.player.LegacyAiPlayer;
import com.jcloisterzone.engine.Game;
import com.jcloisterzone.engine.StateGsonBuilder;
import com.jcloisterzone.figure.*;
import com.jcloisterzone.game.Capability;
import com.jcloisterzone.game.GameSetup;
import com.jcloisterzone.game.GameStatePhaseReducer;
import com.jcloisterzone.game.Rule;
import com.jcloisterzone.game.capability.*;
import com.jcloisterzone.game.phase.GameOverPhase;
import com.jcloisterzone.game.phase.Phase;
import com.jcloisterzone.game.state.GameState;
import com.jcloisterzone.game.state.GameStateBuilder;
import com.jcloisterzone.io.MessageParser;
import com.jcloisterzone.io.message.*;
import io.vavr.collection.HashMap;
import io.vavr.collection.HashSet;
import io.vavr.collection.Map;
import io.vavr.collection.Set;

import java.io.InputStream;
import java.io.PrintStream;
import java.util.ArrayList;
import java.util.Map.Entry;
import java.util.NoSuchElementException;
import java.util.Scanner;

/**
 * AiEngine — a drop-in superset of {@code com.jcloisterzone.engine.Engine} (JCZ 5.x, rev 29a1561) that can
 * host an AI seat.
 *
 * Derived by copy from {@code src/main/java/com/jcloisterzone/engine/Engine.java}; {@code run()} is
 * monolithic over private fields there, so subclassing was not possible. The existing protocol is
 * preserved byte-for-byte:
 *   %load / %bulk / %state / %compat directives, then the GAME_SETUP line, then exactly one state line
 *   per applied message (or only the final one when %bulk on). Dropped from the original: the socket
 *   ({@code -p}) mode, {@code --version}, and {@code -r} reload — stdin/stdout only.
 *
 * ADDED DIRECTIVES
 * ----------------
 *   %ai &lt;playerIndex&gt;   — before GAME_SETUP. Marks that 0-based seat as AI-controlled. No reply.
 *                            May be repeated to make every seat an AI.
 *   %aimove              — compute ONE message from the AI for the current state, apply it through the
 *                            same path as a received message, and print exactly one line:
 *                            {"aiMessage": {"type": "...", "payload": {...}}, "state": {...}}
 *                            On error prints one line {"error": "..."} and applies nothing.
 *
 * Because {@link RankingAiPlayer#apply} returns one message at a time from a buffered chain (tile
 * placement, then meeple placement / pass), the driver calls %aimove repeatedly. That is correct.
 */
public class AiEngine implements Runnable {

    private Scanner in;
    private PrintStream out;
    private PrintStream err;
    private PrintStream log;

    private final Gson gson;
    private MessageParser parser = new MessageParser();

    private Game game;
    private double initialRandom;

    private boolean bulk;

    private ArrayList<String> tileDefinitions = new ArrayList<>();

    // --- AI extension state ---
    private final java.util.Set<Integer> aiSeats = new java.util.LinkedHashSet<>();
    private final java.util.Map<Integer, AiPlayer> aiPlayers = new java.util.HashMap<>();

    private GameState state;
    private GameStatePhaseReducer phaseReducer;

    public AiEngine(InputStream in, PrintStream out, PrintStream err, PrintStream log) {
        this.in = new Scanner(in, "UTF-8");
        this.out = out;
        this.err = err;
        this.log = log;

        gson = new StateGsonBuilder().create();
    }

    private Map<Class<? extends Meeple>, Integer> addMeeples(
            Map<Class<? extends Meeple>, Integer> meeples, GameSetupMessage setupMsg, String key, Class<? extends Meeple> cls) {
        Object cnt = setupMsg.getElements().get(key);
        if (cnt == null) {
            return meeples;
        }
        int count = Integer.parseInt(cnt.toString().split("\\.")[0]);
        if (count <= 0) {
            return meeples;
        }
        return meeples.put(cls, count);
    }

    private Set<Class<? extends Capability<?>>> addCapabilities(
            Set<Class<? extends Capability<?>>> capabilities, GameSetupMessage setupMsg, String key, Class<? extends Capability<?>> cls) {
        Object value = setupMsg.getElements().get(key);
        if (value == null) {
            return capabilities;
        }
        return capabilities.add(cls);
    }

    private GameSetup createSetupFromMessage(GameSetupMessage setupMsg) {
        Map<Class<? extends Meeple>, Integer> meeples = HashMap.empty();
        meeples = addMeeples(meeples, setupMsg, "small-follower", SmallFollower.class);
        meeples = addMeeples(meeples, setupMsg, "abbot", Abbot.class);
        meeples = addMeeples(meeples, setupMsg, "phantom", Phantom.class);
        meeples = addMeeples(meeples, setupMsg, "big-follower", BigFollower.class);
        meeples = addMeeples(meeples, setupMsg, "builder", Builder.class);
        meeples = addMeeples(meeples, setupMsg, "pig", Pig.class);
        meeples = addMeeples(meeples, setupMsg, "barn", Barn.class);
        meeples = addMeeples(meeples, setupMsg, "wagon", Wagon.class);
        meeples = addMeeples(meeples, setupMsg, "mayor", Mayor.class);
        meeples = addMeeples(meeples, setupMsg, "shepherd", Shepherd.class);
        meeples = addMeeples(meeples, setupMsg, "ringmaster", Ringmaster.class);

        Set<Class<? extends Capability<?>>> capabilities = HashSet.empty();
        capabilities = addCapabilities(capabilities, setupMsg,"abbot", AbbotCapability.class);
        capabilities = addCapabilities(capabilities, setupMsg,"barn", BarnCapability.class);
        capabilities = addCapabilities(capabilities, setupMsg,"builder", BuilderCapability.class);
        capabilities = addCapabilities(capabilities, setupMsg,"phantom", PhantomCapability.class);
        capabilities = addCapabilities(capabilities, setupMsg,"shepherd", SheepCapability.class);
        capabilities = addCapabilities(capabilities, setupMsg,"wagon", WagonCapability.class);
        capabilities = addCapabilities(capabilities, setupMsg,"ringmaster", RingmasterCapability.class);

        capabilities = addCapabilities(capabilities, setupMsg,"dragon", DragonCapability.class);
        capabilities = addCapabilities(capabilities, setupMsg,"fairy", FairyCapability.class);
        capabilities = addCapabilities(capabilities, setupMsg,"count", CountCapability.class);
        capabilities = addCapabilities(capabilities, setupMsg,"mage", MageAndWitchCapability.class);

        capabilities = addCapabilities(capabilities, setupMsg,"abbey", AbbeyCapability.class);
        capabilities = addCapabilities(capabilities, setupMsg,"bridge", BridgeCapability.class);
        capabilities = addCapabilities(capabilities, setupMsg,"castle", CastleCapability.class);
        capabilities = addCapabilities(capabilities, setupMsg,"garden", GardenCapability.class);
        capabilities = addCapabilities(capabilities, setupMsg,"tower", TowerCapability.class);
        capabilities = addCapabilities(capabilities, setupMsg,"tunnel", TunnelCapability.class);
        capabilities = addCapabilities(capabilities, setupMsg,"ferry", FerriesCapability.class);
        capabilities = addCapabilities(capabilities, setupMsg,"little-buildings", LittleBuildingsCapability.class);

        capabilities = addCapabilities(capabilities, setupMsg,"traders", TradeGoodsCapability.class);
        capabilities = addCapabilities(capabilities, setupMsg,"king", KingCapability.class);
        capabilities = addCapabilities(capabilities, setupMsg,"robber", RobberCapability.class);
        capabilities = addCapabilities(capabilities, setupMsg,"gold", GoldminesCapability.class);

        capabilities = addCapabilities(capabilities, setupMsg,"princess", PrincessCapability.class);
        capabilities = addCapabilities(capabilities, setupMsg,"portal", PortalCapability.class);
        capabilities = addCapabilities(capabilities, setupMsg,"pig-herd", PigHerdCapability.class);
        capabilities = addCapabilities(capabilities, setupMsg,"bazaar", BazaarCapability.class);
        capabilities = addCapabilities(capabilities, setupMsg,"hill", HillCapability.class);
        capabilities = addCapabilities(capabilities, setupMsg,"vineyard", VineyardCapability.class);
        capabilities = addCapabilities(capabilities, setupMsg,"shrine", ShrineCapability.class);
        capabilities = addCapabilities(capabilities, setupMsg,"festival", FestivalCapability.class);
        capabilities = addCapabilities(capabilities, setupMsg,"big-top", BigTopCapability.class);
        capabilities = addCapabilities(capabilities, setupMsg,"acrobats", AcrobatsCapability.class);

        capabilities = addCapabilities(capabilities, setupMsg,"river", RiverCapability.class);
        capabilities = addCapabilities(capabilities, setupMsg,"corn-circle", CornCircleCapability.class);
        capabilities = addCapabilities(capabilities, setupMsg,"siege", SiegeCapability.class);
        capabilities = addCapabilities(capabilities, setupMsg,"flier", FlierCapability.class);
        capabilities = addCapabilities(capabilities, setupMsg,"church", ChurchCapability.class);
        capabilities = addCapabilities(capabilities, setupMsg,"wind-rose", WindRoseCapability.class);
        capabilities = addCapabilities(capabilities, setupMsg,"monastery", MonasteriesCapability.class);
        capabilities = addCapabilities(capabilities, setupMsg,"russian-trap", RussianPromosTrapCapability.class);
        capabilities = addCapabilities(capabilities, setupMsg,"watchtower", WatchtowerCapability.class);

        capabilities = addCapabilities(capabilities, setupMsg,"robbers-son", RobbersSonCapability.class);

        Map<Rule, Object> rules = HashMap.empty();
        if (setupMsg.getElements().containsKey("farmers")) {
            rules = rules.put(Rule.FARMERS,true);
        }
        if (setupMsg.getElements().containsKey("escape")) {
            rules = rules.put(Rule.ESCAPE, true);
        }

        for (Entry<String, Object> entry : setupMsg.getRules().entrySet()) {
            rules = rules.put(Rule.byKey(entry.getKey()), entry.getValue());
        }

        GameSetup gameSetup = new GameSetup(
                HashMap.ofAll(setupMsg.getSets()),
                HashMap.ofAll(setupMsg.getElements()),
                meeples,
                capabilities,
                rules,
                io.vavr.collection.List.ofAll(setupMsg.getStart())
        );
        return gameSetup;
    }

    private void parseDirective(String line) {
        String[] s = line.split("\\s+", 2);
        var directive = s[0];
        var value = s.length > 1 ? s[1] : null;
        switch (directive) {
            case "%bulk":
                bulk = "on".equals(value);
                if (!bulk) {
                    out.println(gson.toJson(game));
                }
                break;
            case "%compat":
                com.github.zafarkhaja.semver.Version.valueOf(value);
                break;
            case "%load":
                tileDefinitions.add(value);
                break;
            case "%state":
                out.println(gson.toJson(game));
                break;
            case "%ai":
                // ADDED: register an AI seat. Must precede GAME_SETUP. No reply, like %load.
                aiSeats.add(Integer.parseInt(value.trim()));
                break;
            case "%aimove":
                // ADDED: let the AI pick and play one message.
                aiMove();
                break;
            default:
                err.println("#unknown directive " + line);
        }
    }

    /** Emit one single-line JSON error and apply nothing. */
    private void aiError(String msg) {
        out.println("{\"error\":" + gson.toJson(msg) + "}");
    }

    private void aiMove() {
        if (game == null || state == null) {
            aiError("%aimove before game start");
            return;
        }
        if (aiPlayers.isEmpty()) {
            aiError("no AI seat registered (use %ai <playerIndex> before GAME_SETUP)");
            return;
        }
        Player active = state.getActivePlayer();
        if (active == null) {
            aiError("no active player (phase=" + state.getPhase() + ")");
            return;
        }
        AiPlayer ai = aiPlayers.get(active.getIndex());
        if (ai == null) {
            aiError("active player " + active.getIndex() + " is not an AI seat");
            return;
        }

        Message msg;
        try {
            msg = ai.apply(state);
        } catch (RuntimeException ex) {
            aiError("AI failed: " + ex);
            return;
        }
        if (msg == null) {
            aiError("AI produced no message");
            return;
        }

        String aiMessageJson = parser.toJson(msg);
        applyMessage(msg);
        out.println("{\"aiMessage\":" + aiMessageJson + ",\"state\":" + gson.toJson(game) + "}");
    }

    /**
     * The exact body of the main loop's message branch, factored out so %aimove and a received
     * message go through identical bookkeeping (undo marking, replay list, state replacement).
     * Does NOT print — the caller decides.
     */
    private void applyMessage(Message msg) {
        Player oldActivePlayer = state.getActivePlayer();

        if (msg instanceof ReplayableMessage) {
            if (msg instanceof RandomChangingMessage) {
                RandomChangingMessage rndChangeMsg = (RandomChangingMessage) msg;
                if (rndChangeMsg.getRandom() != null) {
                    phaseReducer.getRandomGanerator().setRandom(rndChangeMsg.getRandom());
                }
            }
            state = phaseReducer.apply(state, msg);

            Player newActivePlayer = state.getActivePlayer();
            boolean undoAllowed = (!(msg instanceof RandomChangingMessage) || ((RandomChangingMessage) msg).getRandom() == null)
                    && newActivePlayer != null
                    && newActivePlayer.equals(oldActivePlayer)
                    && !(msg instanceof DeployMeepleMessage && ((DeployMeepleMessage)msg).getMeepleId().contains("shepherd"))
                    && !(msg instanceof MoveNeutralFigureMessage && ((MoveNeutralFigureMessage)msg).getFigureId().contains("dragon"));

            if (undoAllowed) {
                game.markUndo();
            } else {
                game.clearUndo();
            }

            game.replaceState(state);
            game.setReplay(game.getReplay().prepend((ReplayableMessage) msg));
        } else if (msg instanceof UndoMessage) {
            game.undo();
            state = game.getState();
        } else {
            throw new IllegalStateException("Unknown message");
        }
    }

    @Override
    public void run() {
        String line;

        while (true) {
            line = in.nextLine();
            if (log != null) {
                log.println(line);
            }

            if (line.charAt(0) != '%') {
                break;
            }
            parseDirective(line);
        }

        GameSetupMessage setupMsg = (GameSetupMessage) parser.fromJson(line);
        initialRandom = setupMsg.getInitialRandom();

        GameSetup gameSetup = createSetupFromMessage(setupMsg);
        game = new Game(gameSetup);

        phaseReducer = new GameStatePhaseReducer(gameSetup, initialRandom);
        GameStateBuilder builder = new GameStateBuilder(tileDefinitions, gameSetup, setupMsg.getPlayers());

        if (setupMsg.getGameAnnotations() != null) {
            builder.setGameAnnotations(setupMsg.getGameAnnotations());
        }

        state = builder.createInitialState();
        Phase firstPhase = phaseReducer.getFirstPhase();
        state = state.setPhase(firstPhase);
        state = phaseReducer.applyStepResult(firstPhase.enter(state));
        game.replaceState(state);

        // ADDED: instantiate one AI per registered seat, once the initial state exists.
        for (Integer idx : aiSeats) {
            if (idx < 0 || idx >= state.getPlayers().length()) {
                err.println("#%ai seat out of range: " + idx);
                continue;
            }
            Player me = state.getPlayers().getPlayer(idx);
            AiPlayer ai = new LegacyAiPlayer();
            ai.onGameStart(gameSetup, me);
            aiPlayers.put(idx, ai);
        }

        if (!bulk) {
            out.println(gson.toJson(game));
        }

        boolean gameIsOver = false;
        while (!gameIsOver) {
            try {
                line = in.nextLine();
            } catch (NoSuchElementException ex) {
                break;
            }
            if (line.length() == 0) {
                break;
            }

            if (log != null) {
                log.println(line);
            }

            if (line.charAt(0) == '%') {
                parseDirective(line);
                gameIsOver = game.getState().getPhase() instanceof GameOverPhase;
                continue;
            }

            Message msg = parser.fromJson(line);
            applyMessage(msg);

            gameIsOver = game.getState().getPhase() instanceof GameOverPhase;

            if (!bulk || gameIsOver) {
                out.println(gson.toJson(game));
            }
        }
    }

    public static void main(String[] args) {
        AiEngine engine = new AiEngine(System.in, System.out, System.err, null);
        try {
            engine.run();
        } catch (Exception e) {
            e.printStackTrace();
        }
    }
}
