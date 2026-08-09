package com.jcloisterzone.ai;

import java.util.stream.Collectors;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import com.jcloisterzone.Player;
import com.jcloisterzone.game.GameSetup;
import com.jcloisterzone.game.GameStatePhaseReducer;
import com.jcloisterzone.game.capability.PortalCapability;
import com.jcloisterzone.game.state.GameState;
import com.jcloisterzone.io.message.PlaceTileMessage;
import com.jcloisterzone.io.message.RandomChangingMessage;
import com.jcloisterzone.io.message.ReplayableMessage;

import io.vavr.Tuple2;
import io.vavr.collection.Queue;
import io.vavr.collection.Vector;

/**
 * Ported from JCloisterZone 4.x (com.jcloisterzone.ai.RankingAiPlayer) to the 5.x API.
 * The search itself (breadth-first over the action chain within one's own turn, keep the best-ranked
 * terminal chain, then emit it one message at a time) is UNCHANGED.
 *
 * SEMANTIC DEVIATIONS FROM THE 4.x ORIGINAL
 * -----------------------------------------
 * D1. `WsInGameMessage` -> `ReplayableMessage` (package `com.jcloisterzone.io.message`).
 * D5. `WsSaltMessage` -> `RandomChangingMessage`. In 4.x `WsSaltMessage` was the marker interface for
 *     messages carrying a fresh random salt (i.e. messages whose outcome is not deterministic and so
 *     must terminate the AI's look-ahead chain). 5.x renamed exactly that role to `RandomChangingMessage`
 *     (see Engine.run(): it is the interface whose `getRandom()` reseeds the phase reducer). Same role,
 *     same use here: terminate the chain. NOTE the widening — in 5.x `DeployMeepleMessage` *implements*
 *     `RandomChangingMessage` unconditionally (its `random` field is non-null only for FLYING_MACHINE),
 *     so this test now also cuts the chain after ANY meeple deployment. For Base+Farmers this is a
 *     no-op, because deploying a meeple already ends the turn (the `getActivePlayer() != me` test fires
 *     on the same iteration). It WOULD matter for expansions where a deploy is followed by another
 *     own-turn decision.
 */
public abstract class RankingAiPlayer implements AiPlayer {

    protected final transient Logger logger = LoggerFactory.getLogger(getClass());

    private GameStateRanking stateRanking;
    private GameStatePhaseReducer phaseReducer;

    private Player me;
    private Vector<ReplayableMessage> messages = Vector.empty();

    protected abstract GameStateRanking createStateRanking(Player me);

    @Override
    public void onGameStart(GameSetup setup, Player me) {
        this.me = me;
        phaseReducer = new GameStatePhaseReducer(setup, 0);
        stateRanking = createStateRanking(me);
    }

    /** True when the AI still has buffered messages from a previous search. */
    public boolean hasBufferedMessages() {
        return !messages.isEmpty();
    }

    @Override
    public ReplayableMessage apply(GameState state) {
        if (messages.isEmpty()) {
            Double bestSoFar = Double.NEGATIVE_INFINITY;
            Queue<Tuple2<GameState, Vector<ReplayableMessage>>> queue = Queue.of(new Tuple2<>(state, Vector.empty()));

            while (!queue.isEmpty()) {
                Tuple2<Tuple2<GameState, Vector<ReplayableMessage>>, Queue<Tuple2<GameState, Vector<ReplayableMessage>>>> t = queue.dequeue();
                queue = t._2;
                Tuple2<GameState, Vector<ReplayableMessage>> item = t._1;
                GameState itemState = item._1;

                for (ReplayableMessage msg : getPossibleActions(itemState)) {
                    Vector<ReplayableMessage> chain = item._2.append(msg);
                    GameState newState = phaseReducer.apply(itemState, msg);
                    boolean end = newState.getActivePlayer() != me || newState.getTurnPlayer() != state.getTurnPlayer() || msg instanceof RandomChangingMessage;

                    if (!end && msg instanceof PlaceTileMessage &&
                        newState.getLastPlaced().getTile().hasModifier(PortalCapability.MAGIC_PORTAL)) {
                        // hack to avoid bad performance on Portal tile
                        // rank just placement then rang meeple placement separately
                        // still not perfect because it can miss good on tile meeple placement
                        end = true;
                    }

                    if (end) {
                        Double ranking = stateRanking.apply(newState);

//                      String chainStr = chain.map(_msg -> _msg.getClass().getSimpleName()).toJavaStream().collect(Collectors.joining(", "));
//                      System.err.println(String.format(">>> %f\n%s", ranking, chainStr));

                        if (ranking > bestSoFar) {
                            bestSoFar = ranking;
                            messages = chain;
                        }
                    } else {
                        queue = queue.enqueue(new Tuple2<>(newState, chain));
                    }
                }
            }

            if (logger.isDebugEnabled()) {
                String chainStr = messages.map(_msg -> _msg.getClass().getSimpleName()).toJavaStream().collect(Collectors.joining(", "));
                logger.debug(String.format("Best ranking %s, %s", bestSoFar, chainStr));
            }
        }

        ReplayableMessage msg = messages.get();
        messages = messages.drop(1);

        return msg;
    }

}
