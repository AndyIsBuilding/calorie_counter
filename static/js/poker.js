// Poker Statistics Tracker - Client-side JavaScript

let sessionState = SESSION_DATA;
let switchingSeats = false;
let switchFromSeat = null;
let activeHandState = null;
let currentActionSeat = null;
let actionQueue = [];
let cachedActivePlayers = []; // Cached for the duration of a hand

// Initialize on page load
$(document).ready(function() {
    if (sessionState) {
        loadSessionState();
        setupEventHandlers();
    } else {
        setupStartSessionHandlers();
    }
});

function setupStartSessionHandlers() {
    $('#start-session-btn, #start-session-btn-main').on('click', function() {
        showButtonSelector();
    });
}

function showButtonSelector() {
    $('#button-modal').removeClass('hidden');
    
    $('.btn-position-select').on('click', function() {
        const position = $(this).data('position');
        startSession(position);
    });
    
    $('#cancel-button-select').on('click', function() {
        $('#button-modal').addClass('hidden');
    });
}

function startSession(buttonPosition) {
    $.post('/poker/start_session', {
        button_position: buttonPosition
    })
    .done(function(response) {
        if (response.success) {
            setTimeout(() => location.reload(), 1000);
        }
    })
    .fail(function() {
        showToast('Failed to start session', 'error');
    });
}

function setupEventHandlers() {
    // End session
    $('#end-session-btn').on('click', function() {
        if (confirm('Are you sure you want to end this session?')) {
            endSession();
        }
    });
    
    // Skip hand
    $('#skip-hand-btn').on('click', function() {
        skipHand();
    });
    
    // Undo action
    $('#undo-action-btn').on('click', function() {
        undoAction();
    });
    
    // Action buttons
    $('.action-btn').on('click', function() {
        const action = $(this).data('action');
        recordAction(currentActionSeat, action);
    });
    
    // Seat clicks
    $('.poker-seat').on('click', function() {
        const seat = $(this).data('seat');
        handleSeatClick(seat);
    });

    // Straddle toggles: only one can be active at a time
    $('#btn-straddle-toggle').on('change', function() {
        if ($(this).is(':checked')) $('#utg-straddle-toggle').prop('checked', false);
        updateBlindPositions();
        if (!activeHandState) updateActionQueue();
    });
    $('#utg-straddle-toggle').on('change', function() {
        if ($(this).is(':checked')) $('#btn-straddle-toggle').prop('checked', false);
        updateBlindPositions();
        if (!activeHandState) updateActionQueue();
    });
}

function loadSessionState() {
    // Update button position indicators
    updateButtonPosition(sessionState.button_position);

    // Load players if session data has them
    if (sessionState.players) {
        sessionState.players.forEach(player => {
            updateSeatDisplay(player);
        });
        // Cache active players from initial data
        cachedActivePlayers = sessionState.players
            .filter(p => !p.sitting_out)
            .map(p => p.seat_number)
            .sort((a, b) => a - b);
    } else {
        // Fetch current state
        refreshSessionState();
    }

    // Check if there's an active hand
    if (sessionState.active_hand) {
        showActing();
        loadActiveHand(sessionState.active_hand);
    } else {
        showStraddle();
        updateActionQueue();
    }

    updateBlindPositions();
}

function refreshSessionState() {
    $.get('/poker/session_state')
    .done(function(response) {
        if (response.success) {
            // Update session info
            $('#hand-count').text(response.session.hand_count);
            sessionState.session_id = response.session.id;
            sessionState.button_position = response.session.button_position;

            // Update button position
            updateButtonPosition(response.session.button_position);

            // Update players and cache active list
            response.players.forEach(player => {
                updateSeatDisplay(player);
            });
            cachedActivePlayers = response.players
                .filter(p => !p.sitting_out)
                .map(p => p.seat_number)
                .sort((a, b) => a - b);

            // Update active hand state
            if (response.active_hand) {
                activeHandState = response.active_hand;
                showActing();
                updateActionQueue();
            } else {
                activeHandState = null;
                showStraddle();
                updateActionQueue();
            }

            updateBlindPositions();
        }
    });
}

function updateButtonPosition(position) {
    const $table = $('.poker-table');
    for (let i = 1; i <= 9; i++) {
        $table.removeClass('btn-at-' + i);
    }
    if (position) {
        $table.addClass('btn-at-' + position);
    }
}

function updateBlindPositions() {
    const $table = $('.poker-table');
    for (let i = 1; i <= 9; i++) {
        $table.removeClass('sb-at-' + i + ' bb-at-' + i + ' str-at-' + i);
    }

    if (!sessionState || !cachedActivePlayers || cachedActivePlayers.length < 2) return;

    const buttonPos = sessionState.button_position;
    const sb = getNextActiveSeat(buttonPos, cachedActivePlayers);
    const bb = getNextActiveSeat(sb, cachedActivePlayers);

    if (sb) $table.addClass('sb-at-' + sb);
    if (bb) $table.addClass('bb-at-' + bb);

    // Straddle: use active hand state if mid-hand, otherwise check toggles
    const hasBtnStraddle = activeHandState
        ? activeHandState.has_btn_straddle
        : $('#btn-straddle-toggle').is(':checked');
    const hasUtgStraddle = activeHandState
        ? activeHandState.has_utg_straddle
        : $('#utg-straddle-toggle').is(':checked');

    if (hasBtnStraddle) {
        $table.addClass('str-at-' + buttonPos);
    } else if (hasUtgStraddle) {
        const utg = getNextActiveSeat(bb, cachedActivePlayers);
        if (utg) $table.addClass('str-at-' + utg);
    }
}

function updateSeatDisplay(player) {
    const seat = player.seat_number;
    const $seat = $(`.poker-seat[data-seat="${seat}"]`);
    
    // Show player info
    $seat.find('.empty-seat').addClass('hidden');
    $seat.find('.player-info').removeClass('hidden');
    
    // Set player name
    const playerName = player.name || `Player ${seat}`;
    $seat.find('.player-name').text(playerName);
    
    // Mark placeholder players visually
    if (playerName.startsWith('Player ')) {
        $seat.addClass('placeholder-player');
    } else {
        $seat.removeClass('placeholder-player');
    }
    
    // Calculate and display session stats
    const sessionVpip = player.session_hands > 0 
        ? Math.round((player.session_vpip / player.session_hands) * 100) 
        : 0;
    const sessionPfr = player.session_hands > 0 
        ? Math.round((player.session_pfr / player.session_hands) * 100) 
        : 0;
    
    $seat.find('.session-vpip').text(sessionVpip + '%');
    $seat.find('.session-pfr').text(sessionPfr + '%');
    
    // Show overall stats if player is named
    if (player.total_hands && player.total_hands > 0) {
        const overallVpip = Math.round((player.total_vpip / player.total_hands) * 100);
        const overallPfr = Math.round((player.total_pfr / player.total_hands) * 100);
        
        $seat.find('.overall-vpip').text(overallVpip + '%');
        $seat.find('.overall-pfr').text(overallPfr + '%');
        $seat.find('.player-overall').removeClass('hidden');
    } else {
        $seat.find('.player-overall').addClass('hidden');
    }
    
    // Show/hide sitting out indicator
    if (player.sitting_out) {
        $seat.find('.sitting-out-indicator').removeClass('hidden');
        $seat.addClass('sitting-out');
    } else {
        $seat.find('.sitting-out-indicator').addClass('hidden');
        $seat.removeClass('sitting-out');
    }
}

function clearSeatDisplay(seat) {
    const $seat = $(`.poker-seat[data-seat="${seat}"]`);
    
    $seat.find('.empty-seat').removeClass('hidden');
    $seat.find('.player-info').addClass('hidden');
    $seat.find('.sitting-out-indicator').addClass('hidden');
    $seat.removeClass('sitting-out placeholder-player');
}

function handleSeatClick(seat) {
    const $seat = $(`.poker-seat[data-seat="${seat}"]`);
    const isEmpty = $seat.find('.empty-seat').is(':visible');
    
    if (switchingSeats) {
        // Complete seat switch
        if (isEmpty && seat !== switchFromSeat) {
            switchSeats(switchFromSeat, seat);
        }
        cancelSeatSwitch();
        return;
    }
    
    if (isEmpty) {
        showAddPlayerModal(seat);
    } else {
        showPlayerManagementModal(seat);
    }
}

function showAddPlayerModal(seat) {
    const modalContent = `
        <div class="space-y-4">
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-2">Player Name</label>
                <input type="text" id="new-player-name" class="w-full px-3 py-2 border border-gray-300 rounded-md" placeholder="Enter name (optional)">
            </div>
            <div class="text-sm text-gray-600">
                Or select an existing player:
            </div>
            <div>
                <input type="text" id="search-players" class="w-full px-3 py-2 border border-gray-300 rounded-md" placeholder="Search players...">
                <div id="player-search-results" class="mt-2 max-h-40 overflow-y-auto"></div>
            </div>
            <div class="flex gap-2">
                <button id="add-player-btn" class="btn btn-primary flex-1">Add Player</button>
                <button id="close-modal-btn" class="btn btn-secondary flex-1">Cancel</button>
            </div>
        </div>
    `;
    
    $('#modal-content').html(modalContent);
    $('#player-modal').removeClass('hidden');
    
    $('#add-player-btn').on('click', function() {
        const name = $('#new-player-name').val().trim();
        addPlayer(seat, name);
    });
    
    $('#close-modal-btn').on('click', closeModal);
    
    // Player search
    $('#search-players').on('input', debounce(function() {
        const query = $('#search-players').val().trim();
        if (query.length > 0) {
            searchPlayers(query, seat);
        } else {
            $('#player-search-results').empty();
        }
    }, 300));
}

function showPlayerManagementModal(seat) {
    const $seat = $(`.poker-seat[data-seat="${seat}"]`);
    const playerName = $seat.find('.player-name').text();
    const isPlaceholder = playerName.startsWith('Player ');
    
    let modalContent = `
        <div class="space-y-3">
    `;
    
    // If it's a placeholder, emphasize replacing with known player
    if (isPlaceholder) {
        modalContent += `
            <button class="btn btn-primary w-full" data-action="search">Replace with Known Player</button>
            <div class="border-t border-gray-200 my-2"></div>
        `;
    }
    
    modalContent += `
            <button class="btn btn-secondary w-full" data-action="name">Name/Update Player</button>
            <button class="btn btn-secondary w-full" data-action="switch">Switch Seats</button>
            <button class="btn btn-secondary w-full" data-action="sitting-out">Toggle Sitting Out</button>
            <button class="btn btn-error w-full" data-action="remove">Remove Player</button>
            <button class="btn btn-secondary w-full" data-action="cancel">Cancel</button>
        </div>
    `;
    
    $('#modal-content').html(modalContent);
    $('#player-modal').removeClass('hidden');
    
    $('#modal-content button').on('click', function() {
        const action = $(this).data('action');
        
        switch(action) {
            case 'search':
                closeModal();
                showSearchReplaceModal(seat);
                break;
            case 'name':
                closeModal();
                showNamePlayerModal(seat);
                break;
            case 'switch':
                closeModal();
                initiateSeatSwitch(seat);
                break;
            case 'sitting-out':
                toggleSittingOut(seat);
                closeModal();
                break;
            case 'remove':
                removePlayer(seat);
                closeModal();
                break;
            case 'cancel':
                closeModal();
                break;
        }
    });
}

function showSearchReplaceModal(seat) {
    const modalContent = `
        <div class="space-y-4">
            <p class="text-sm text-gray-600">Search for a player you've played with before to load their statistics:</p>
            <div>
                <input type="text" id="search-replace-input" class="w-full px-3 py-2 border border-gray-300 rounded-md" placeholder="Search player name...">
            </div>
            <div id="search-replace-results" class="max-h-60 overflow-y-auto"></div>
            <button id="close-modal-btn" class="btn btn-secondary w-full">Cancel</button>
        </div>
    `;
    
    $('#modal-content').html(modalContent);
    $('#player-modal').removeClass('hidden');
    
    $('#close-modal-btn').on('click', closeModal);
    
    // Focus the search input
    $('#search-replace-input').focus();
    
    // Player search with replace functionality
    $('#search-replace-input').on('input', debounce(function() {
        const query = $('#search-replace-input').val().trim();
        if (query.length > 0) {
            searchPlayersForReplace(query, seat);
        } else {
            $('#search-replace-results').html('<p class="text-sm text-gray-500 p-2">Start typing to search...</p>');
        }
    }, 300));
}

function searchPlayersForReplace(query, targetSeat) {
    $.get('/poker/search_players', { q: query })
    .done(function(response) {
        if (response.success) {
            const results = response.players;
            let html = '';
            
            if (results.length === 0) {
                html = '<p class="text-sm text-gray-500 p-2">No players found</p>';
            } else {
                results.forEach(player => {
                    html += `
                        <div class="p-3 hover:bg-gray-100 cursor-pointer border-b player-replace-item" data-player-id="${player.id}" data-player-name="${player.name}">
                            <div class="font-medium">${player.name}</div>
                            <div class="text-xs text-gray-600">
                                VPIP: ${player.vpip}% | PFR: ${player.pfr}% | 
                                Hands: ${player.total_hands} | 
                                Last: ${player.last_played || 'N/A'}
                            </div>
                        </div>
                    `;
                });
            }
            
            $('#search-replace-results').html(html);
            
            $('.player-replace-item').on('click', function() {
                const playerId = $(this).data('player-id');
                const playerName = $(this).data('player-name');
                replacePlayerWithKnown(targetSeat, playerId, playerName);
            });
        }
    });
}

function replacePlayerWithKnown(seat, playerId, playerName) {
    // First remove the current placeholder
    $.post('/poker/remove_player', {
        session_id: sessionState.session_id,
        seat_number: seat
    })
    .done(function(removeResponse) {
        if (removeResponse.success) {
            // Then add the known player
            $.post('/poker/add_player', {
                session_id: sessionState.session_id,
                seat_number: seat,
                player_name: playerName,
                player_id: playerId
            })
            .done(function(addResponse) {
                if (addResponse.success) {
                    refreshSessionState();
                    closeModal();
                }
            });
        }
    });
}

function showNamePlayerModal(seat) {
    const $seat = $(`.poker-seat[data-seat="${seat}"]`);
    const currentName = $seat.find('.player-name').text();
    
    const modalContent = `
        <div class="space-y-4">
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-2">Player Name *</label>
                <input type="text" id="player-name-input" class="w-full px-3 py-2 border border-gray-300 rounded-md" value="${currentName}">
            </div>
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-2">Notes (Optional)</label>
                <textarea id="player-notes-input" class="w-full px-3 py-2 border border-gray-300 rounded-md" rows="3" placeholder="Player tendencies, observations..."></textarea>
            </div>
            <div class="flex gap-2">
                <button id="save-player-btn" class="btn btn-primary flex-1">Save</button>
                <button id="close-modal-btn" class="btn btn-secondary flex-1">Cancel</button>
            </div>
        </div>
    `;
    
    $('#modal-content').html(modalContent);
    $('#player-modal').removeClass('hidden');
    
    $('#save-player-btn').on('click', function() {
        const name = $('#player-name-input').val().trim();
        const notes = $('#player-notes-input').val().trim();
        namePlayer(seat, name, notes);
    });
    
    $('#close-modal-btn').on('click', closeModal);
}

function closeModal() {
    $('#player-modal').addClass('hidden');
}

function addPlayer(seat, name, playerId = null) {
    const data = {
        session_id: sessionState.session_id,
        seat_number: seat,
        player_name: name
    };
    
    if (playerId) {
        data.player_id = playerId;
    }
    
    $.post('/poker/add_player', data)
    .done(function(response) {
        if (response.success) {
            refreshSessionState();
            closeModal();
        }
    });
}

function removePlayer(seat) {
    if (!confirm('Remove this player from the session?')) return;
    
    $.post('/poker/remove_player', {
        session_id: sessionState.session_id,
        seat_number: seat
    })
    .done(function(response) {
        if (response.success) {
            clearSeatDisplay(seat);
        }
    });
}

function namePlayer(seat, name, notes) {
    if (!name) {
        showToast('Player name is required', 'error');
        return;
    }
    
    $.post('/poker/name_player', {
        session_id: sessionState.session_id,
        seat_number: seat,
        player_name: name,
        player_notes: notes
    })
    .done(function(response) {
        if (response.success) {
            refreshSessionState();
            closeModal();
        }
    });
}

function initiateSeatSwitch(fromSeat) {
    switchingSeats = true;
    switchFromSeat = fromSeat;
    
    $(`.poker-seat[data-seat="${fromSeat}"]`).addClass('switching-from');
    $('.poker-seat').addClass('switch-mode');
    
    showToast('Click destination seat or click again to cancel', 'info');
}

function cancelSeatSwitch() {
    switchingSeats = false;
    $(`.poker-seat[data-seat="${switchFromSeat}"]`).removeClass('switching-from');
    $('.poker-seat').removeClass('switch-mode');
    switchFromSeat = null;
}

function switchSeats(fromSeat, toSeat) {
    $.post('/poker/switch_seats', {
        session_id: sessionState.session_id,
        from_seat: fromSeat,
        to_seat: toSeat
    })
    .done(function(response) {
        if (response.success) {
            refreshSessionState();
        }
    });
}

function toggleSittingOut(seat) {
    $.post('/poker/toggle_sitting_out', {
        session_id: sessionState.session_id,
        seat_number: seat
    })
    .done(function(response) {
        if (response.success) {
            refreshSessionState();
        }
    });
}

function searchPlayers(query, targetSeat) {
    $.get('/poker/search_players', { q: query })
    .done(function(response) {
        if (response.success) {
            const results = response.players;
            let html = '';
            
            if (results.length === 0) {
                html = '<p class="text-sm text-gray-500 p-2">No players found</p>';
            } else {
                results.forEach(player => {
                    html += `
                        <div class="p-2 hover:bg-gray-100 cursor-pointer border-b player-search-item" data-player-id="${player.id}">
                            <div class="font-medium">${player.name}</div>
                            <div class="text-xs text-gray-600">
                                VPIP: ${player.vpip}% | PFR: ${player.pfr}% | 
                                Hands: ${player.total_hands} | 
                                Last: ${player.last_played || 'N/A'}
                            </div>
                        </div>
                    `;
                });
            }
            
            $('#player-search-results').html(html);
            
            $('.player-search-item').on('click', function() {
                const playerId = $(this).data('player-id');
                const playerName = $(this).find('.font-medium').text();
                addPlayer(targetSeat, playerName, playerId);
            });
        }
    });
}

function recordAction(seat, action) {
    if (!seat) {
        showToast('No player to act', 'error');
        return;
    }

    if (!activeHandState) {
        // No active hand — start one first using current straddle settings
        const btnStraddle = $('#btn-straddle-toggle').is(':checked') ? 1 : 0;
        const utgStraddle = $('#utg-straddle-toggle').is(':checked') ? 1 : 0;

        $.get('/poker/session_state')
        .done(function(stateResponse) {
            if (!stateResponse.success) return;

            cachedActivePlayers = stateResponse.players
                .filter(p => !p.sitting_out)
                .map(p => p.seat_number)
                .sort((a, b) => a - b);

            if (cachedActivePlayers.length < 2) {
                showToast('Need at least 2 active players', 'error');
                return;
            }

            $.post('/poker/start_hand', {
                session_id: sessionState.session_id,
                has_btn_straddle: btnStraddle,
                has_utg_straddle: utgStraddle
            })
            .done(function(response) {
                if (response.success) {
                    $('.poker-seat').removeClass('action-fold action-raise action-call');
                    activeHandState = {
                        hand_number: response.hand_number,
                        has_btn_straddle: btnStraddle === 1,
                        has_utg_straddle: utgStraddle === 1,
                        actions: []
                    };
                    showActing();
                    doRecordAction(seat, action);
                }
            });
        });
        return;
    }

    doRecordAction(seat, action);
}

function doRecordAction(seat, action) {
    $.post('/poker/record_action', {
        session_id: sessionState.session_id,
        seat_number: seat,
        action: action
    })
    .done(function(response) {
        if (response.success) {
            // Apply action color to the seat
            const $seat = $(`.poker-seat[data-seat="${seat}"]`);
            $seat.removeClass('action-fold action-raise action-call active-action');
            if (action === 'fold') $seat.addClass('action-fold');
            else if (action === 'raise') $seat.addClass('action-raise');
            else if (action === 'call' || action === 'check') $seat.addClass('action-call');

            activeHandState.actions.push({ seat: seat, action: action });
            updateActionQueue();
        }
    });
}

function completeHand() {
    $.post('/poker/complete_hand', {
        session_id: sessionState.session_id
    })
    .done(function(response) {
        if (response.success) {
            $('.poker-seat').removeClass('action-fold action-raise action-call');
            $('#hand-count').text(response.hand_count);
            updateButtonPosition(response.new_button_position);
            sessionState.button_position = response.new_button_position;
            activeHandState = null;
            showStraddle();

            // Reset straddle toggles
            $('#btn-straddle-toggle, #utg-straddle-toggle').prop('checked', false);

            // Refresh to get updated stats and highlight next first-to-act
            refreshSessionState();
        }
    });
}

function skipHand() {
    if (!confirm('Skip this hand? Button will move but no stats will be recorded.')) return;
    
    $.post('/poker/skip_hand', {
        session_id: sessionState.session_id
    })
    .done(function(response) {
        if (response.success) {
            updateButtonPosition(response.new_button_position);
            sessionState.button_position = response.new_button_position;
            activeHandState = null;
            showStraddle();
            updateBlindPositions();
            updateActionQueue();
        }
    });
}

function undoAction() {
    $.post('/poker/undo_action', {
        session_id: sessionState.session_id
    })
    .done(function(response) {
        if (response.success) {
            if (activeHandState && activeHandState.actions.length > 0) {
                const undone = activeHandState.actions.pop();
                // Recalculate action colors from scratch
                $('.poker-seat').removeClass('action-fold action-raise action-call');
                activeHandState.actions.forEach(a => {
                    const $s = $(`.poker-seat[data-seat="${a.seat}"]`);
                    $s.removeClass('action-fold action-raise action-call');
                    if (a.action === 'fold') $s.addClass('action-fold');
                    else if (a.action === 'raise') $s.addClass('action-raise');
                    else if (a.action === 'call' || a.action === 'check') $s.addClass('action-call');
                });
            }
            updateActionQueue();
        }
    });
}

function endSession() {
    $.post('/poker/end_session', {
        session_id: sessionState.session_id
    })
    .done(function(response) {
        if (response.success) {
            setTimeout(() => location.reload(), 1500);
        }
    });
}

function showStraddle() {
    $('#straddle-options').removeClass('hidden');
    $('#acting-indicator').addClass('hidden');
}

function showActing() {
    $('#straddle-options').addClass('hidden');
    $('#acting-indicator').removeClass('hidden');
}

function loadActiveHand(hand) {
    activeHandState = hand;
    updateActionQueue();
}

function getNextActiveSeat(currentSeat, activePlayers) {
    // Find the next active seat clockwise from currentSeat (not including currentSeat)
    for (let i = 1; i <= 9; i++) {
        const candidate = ((currentSeat - 1 + i) % 9) + 1;
        if (activePlayers.includes(candidate)) {
            return candidate;
        }
    }
    return null;
}

function getLastOptionSeat(buttonPos, activePlayers, hasBtnStraddle, hasUtgStraddle) {
    // Returns the seat that gets to check if no raise has occurred.
    // In a normal hand: BB is last to act with the option.
    // With BTN straddle: the button is last to act with the option.
    // With UTG straddle: UTG is last to act with the option.
    const sb = getNextActiveSeat(buttonPos, activePlayers);
    const bb = getNextActiveSeat(sb, activePlayers);
    if (hasBtnStraddle) {
        return buttonPos;
    } else if (hasUtgStraddle) {
        return getNextActiveSeat(bb, activePlayers); // UTG
    } else {
        return bb;
    }
}

function buildActionOrder(buttonPos, activePlayers, hasBtnStraddle, hasUtgStraddle) {
    // Determine first to act preflop:
    // No straddle: UTG = button + 3 (skip SB +1, BB +2)
    // UTG straddle: UTG+1 = button + 4 (skip SB, BB, UTG straddle)
    // BTN straddle: SB = button + 1
    let firstSeat;
    if (hasBtnStraddle) {
        // SB acts first (seat after button)
        firstSeat = getNextActiveSeat(buttonPos, activePlayers);
    } else if (hasUtgStraddle) {
        // First player after UTG (button+3 is UTG, so skip to button+4 equivalent)
        const sb = getNextActiveSeat(buttonPos, activePlayers);
        const bb = getNextActiveSeat(sb, activePlayers);
        const utg = getNextActiveSeat(bb, activePlayers);
        firstSeat = getNextActiveSeat(utg, activePlayers);
    } else {
        // UTG = first player after BB (button -> SB -> BB -> UTG)
        const sb = getNextActiveSeat(buttonPos, activePlayers);
        const bb = getNextActiveSeat(sb, activePlayers);
        firstSeat = getNextActiveSeat(bb, activePlayers);
    }

    // Build full action order starting from firstSeat
    const order = [firstSeat];
    let seat = firstSeat;
    for (let i = 0; i < activePlayers.length - 1; i++) {
        seat = getNextActiveSeat(seat, activePlayers);
        order.push(seat);
    }
    return order;
}

function updateActionQueue() {
    if (!activeHandState) {
        // Pre-hand: highlight the first player who will act so the user knows who to record
        if (!sessionState || !cachedActivePlayers || cachedActivePlayers.length < 2) {
            currentActionSeat = null;
            $('.poker-seat').removeClass('active-action');
            return;
        }
        const btnStraddle = $('#btn-straddle-toggle').is(':checked');
        const utgStraddle = $('#utg-straddle-toggle').is(':checked');
        const order = buildActionOrder(sessionState.button_position, cachedActivePlayers, btnStraddle, utgStraddle);
        currentActionSeat = order[0] || null;
        $('.poker-seat').removeClass('active-action');
        if (currentActionSeat) {
            $(`.poker-seat[data-seat="${currentActionSeat}"]`).addClass('active-action');
        }
        return;
    }

    const buttonPos = sessionState.button_position;
    const activePlayers = cachedActivePlayers;

    if (activePlayers.length < 2) {
        showToast('Need at least 2 active players', 'error');
        return;
    }

    const actionOrder = buildActionOrder(
        buttonPos, activePlayers,
        activeHandState.has_btn_straddle, activeHandState.has_utg_straddle
    );

    const actions = activeHandState.actions;

    // Determine who still needs to act.
    // Players who folded are out. Action continues until everyone remaining
    // has called the last raise (or there was no raise and everyone has acted).
    const foldedSeats = new Set();
    let lastRaiseIndex = -1; // Index in actions[] of the most recent raise
    const skippedSeats = new Set();

    for (let i = 0; i < actions.length; i++) {
        const a = actions[i];
        if (a.action === 'fold') foldedSeats.add(a.seat);
        if (a.action === 'raise') lastRaiseIndex = i;
        if (a.action === 'skip') skippedSeats.add(a.seat);
    }

    // Remaining players = active minus folded minus skipped
    const remaining = actionOrder.filter(s => !foldedSeats.has(s) && !skippedSeats.has(s));

    if (remaining.length <= 1) {
        // Everyone folded except one — auto-complete
        $('.poker-seat').removeClass('active-action');
        currentActionSeat = null;
        completeHand();
        return;
    }

    // Find who needs to act next.
    // If there was a raise, everyone after it (in action order) who hasn't folded/called must act.
    // If no raise, each player acts once.
    let nextSeat = null;

    if (lastRaiseIndex === -1) {
        // No raise yet — find first remaining player who hasn't acted at all
        const actedSeats = new Set(actions.map(a => a.seat));
        for (const seat of actionOrder) {
            if (!foldedSeats.has(seat) && !skippedSeats.has(seat) && !actedSeats.has(seat)) {
                nextSeat = seat;
                break;
            }
        }
    } else {
        // There was a raise — find the first remaining player after the last raiser
        // who hasn't responded to that raise (hasn't acted after lastRaiseIndex)
        const lastRaiserSeat = actions[lastRaiseIndex].seat;
        const actedAfterRaise = new Set();
        for (let i = lastRaiseIndex + 1; i < actions.length; i++) {
            actedAfterRaise.add(actions[i].seat);
        }

        // Walk the action order starting from the player after the last raiser
        const raiserIdx = actionOrder.indexOf(lastRaiserSeat);
        for (let i = 1; i < actionOrder.length; i++) {
            const seat = actionOrder[(raiserIdx + i) % actionOrder.length];
            if (seat === lastRaiserSeat) continue; // Back to raiser = done
            if (foldedSeats.has(seat) || skippedSeats.has(seat)) continue;
            if (!actedAfterRaise.has(seat)) {
                nextSeat = seat;
                break;
            }
        }
    }

    if (nextSeat) {
        currentActionSeat = nextSeat;
        const playerName = $(`.poker-seat[data-seat="${currentActionSeat}"] .player-name`).text();
        $('#current-action-player').text(`Seat ${currentActionSeat} (${playerName})`);

        $('.poker-seat').removeClass('active-action');
        $(`.poker-seat[data-seat="${currentActionSeat}"]`).addClass('active-action');

        // Show "Check" instead of "Call" when the last-option seat gets to act with no raise
        const lastOptionSeat = getLastOptionSeat(
            buttonPos, activePlayers,
            activeHandState.has_btn_straddle, activeHandState.has_utg_straddle
        );
        const $callBtn = $('[data-action="call"], [data-action="check"]');
        if (nextSeat === lastOptionSeat && lastRaiseIndex === -1) {
            $callBtn.text('Check').attr('data-action', 'check');
        } else {
            $callBtn.text('Call').attr('data-action', 'call');
        }
    } else {
        // All remaining players have acted — auto-complete the hand
        $('.poker-seat').removeClass('active-action');
        currentActionSeat = null;
        $('[data-action="call"], [data-action="check"]').text('Call').attr('data-action', 'call');
        completeHand();
    }
}

// Utility: Debounce function
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

