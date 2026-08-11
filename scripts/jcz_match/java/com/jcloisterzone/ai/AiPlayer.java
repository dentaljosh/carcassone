package com.jcloisterzone.ai;

import com.jcloisterzone.Player;
import com.jcloisterzone.action.PlayerAction;
import com.jcloisterzone.game.GameSetup;
import com.jcloisterzone.game.state.ActionsState;
import com.jcloisterzone.game.state.GameState;
import com.jcloisterzone.io.message.PassMessage;
import com.jcloisterzone.io.message.ReplayableMessage;

import io.vavr.Function1;
import io.vavr.collection.Vector;

/**
 * Ported from JCloisterZone 4.x (com.jcloisterzone.ai.AiPlayer) to the 5.x API.
 *
 * SEMANTIC DEVIATIONS FROM THE 4.x ORIGINAL
 * -----------------------------------------
 * D1. `com.jcloisterzone.wsio.message.WsInGameMessage` -> `com.jcloisterzone.io.message.ReplayableMessage`.
 *     5.x's `GameStatePhaseReducer.apply(GameState, Message)` accepts `Message`, but the engine main loop
 *     only replays/undo-tracks `ReplayableMessage`, which is exactly the 4.x `WsInGameMessage` role.
 *     Every message the 4.x actions could produce is a `ReplayableMessage` in 5.x. No behaviour change.
 * D2. `SupportedSetup supportedSetup()` DELETED — `com.jcloisterzone.game.SupportedSetup` does not exist
 *     in 5.x (client-only concept). The AI no longer advertises which capabilities it supports; the caller
 *     is responsible for only seating it in a supported game. THIS IS A REAL LOSS OF A SAFETY CHECK.
 * D3. 5.x removed `PlayerAction.select(option)` (the action -> message factory lived on the action object in
 *     4.x; in 5.x the JS client builds messages itself). The dispatch is therefore reimplemented here in
 *     `Helpers.createMessage`, transcribed one-for-one from each 4.x action's `select()` body. See
 *     `Helpers` for the per-action notes, including the three actions that cannot be reproduced.
 * D4. `getPossibleActions` now skips actions whose `getOptions()` is null. 5.x `ConfirmAction`,
 *     `FlockAction`, `CornCircleSelectDeployOrRemoveAction` and `BazaarSelectBuyOrSellAction` are
 *     `AbstractPlayerAction<Void>` constructed with `null` options, which would NPE the 4.x loop.
 *     None of these occur in Base+Farmers.
 */
public interface AiPlayer extends Function1<GameState, ReplayableMessage> {

    default void onGameStart(GameSetup setup, Player me) {
    }

    default Vector<ReplayableMessage> getPossibleActions(GameState state) {
        ActionsState as = state.getPlayerActions();

        Vector<ReplayableMessage> messages = as.getActions().flatMap(
            action -> MessageFactory.createMessages(action)
        );

        if (as.isPassAllowed()) {
            messages = messages.append(new PassMessage());
        }

        return messages;
    }

    static class Helpers {
        @SuppressWarnings({ "rawtypes", "unchecked" })
        public static ReplayableMessage createMessage(PlayerAction action, Object option) {
            return MessageFactory.createMessage(action, option);
        }
    }
}
