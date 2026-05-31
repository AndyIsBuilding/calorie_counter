// Poker Statistics Tracker - Client-side JavaScript

let sessionState = SESSION_DATA;
let switchingSeats = false;
let switchFromSeat = null;
let activeHandState = null;
let currentActionSeat = null;
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
            setTimeout(() => location.reload(), 800);
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

    // Start a hand (explicit) — locks in straddle settings, enters recording mode
    $('#start-hand-btn').on('click', startHand);

    // Ready-state "Skip": advance the button without recording a hand (no prompt,
    // so you can walk the button several seats with repeated taps).
    $('#skip-hand-setup-btn').on('click', function() { skipHand(false); });

    // Mid-hand "Misdeal": discards the in-progress hand and advances the button.
    $('#skip-hand-btn').on('click', function() { skipHand(true); });

    // Undo last recorded action
    $('#undo-action-btn').on('click', undoAction);

    // Action buttons live in the fixed centre panel; they act on the highlighted
    // seat. Read the live attribute (not .data()) so the Call/Check relabel sticks.
    $('#center-action').on('click', '.ov-btn', function(e) {
        e.stopPropagation();
        const action = $(this).attr('data-action');
        recordAction(currentActionSeat, action);
    });

    // Seat clicks (player management) — only when not mid-hand
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
    updateButtonPosition(sessionState.button_position);

    if (sessionState.players) {
        sessionState.players.forEach(player => updateSeatDisplay(player));
        cachedActivePlayers = sessionState.players
            .filter(p => !p.sitting_out)
            .map(p => p.seat_number)
            .sort((a, b) => a - b);
    } else {
        refreshSessionState();
    }

    if (sessionState.active_hand) {
        activeHandState = sessionState.active_hand;
        // Repaint action colours from saved actions
        repaintActionColors(activeHandState.actions);
        showActing();
        updateActionQueue();
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
            $('#hand-count').text(response.session.hand_count);
            $('#felt-hand-num').text(response.session.hand_count + 1);
            sessionState.session_id = response.session.id;
            sessionState.button_position = response.session.button_position;

            updateButtonPosition(response.session.button_position);

            response.players.forEach(player => updateSeatDisplay(player));
            cachedActivePlayers = response.players
                .filter(p => !p.sitting_out)
                .map(p => p.seat_number)
                .sort((a, b) => a - b);

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

// --- Position markers (placed directly on seats) ---

function updateButtonPosition(position) {
    $('.poker-seat').removeClass('is-btn');
    if (position) {
        $(`.poker-seat[data-seat="${position}"]`).addClass('is-btn');
    }
}

function updateBlindPositions() {
    $('.poker-seat').removeClass('is-sb is-bb is-str');

    if (!sessionState || !cachedActivePlayers || cachedActivePlayers.length < 2) return;

    const buttonPos = sessionState.button_position;
    const sb = getNextActiveSeat(buttonPos, cachedActivePlayers);
    const bb = getNextActiveSeat(sb, cachedActivePlayers);

    if (sb) $(`.poker-seat[data-seat="${sb}"]`).addClass('is-sb');
    if (bb) $(`.poker-seat[data-seat="${bb}"]`).addClass('is-bb');

    const hasBtnStraddle = activeHandState
        ? activeHandState.has_btn_straddle
        : $('#btn-straddle-toggle').is(':checked');
    const hasUtgStraddle = activeHandState
        ? activeHandState.has_utg_straddle
        : $('#utg-straddle-toggle').is(':checked');

    if (hasBtnStraddle) {
        $(`.poker-seat[data-seat="${buttonPos}"]`).addClass('is-str');
    } else if (hasUtgStraddle) {
        const utg = getNextActiveSeat(bb, cachedActivePlayers);
        if (utg) $(`.poker-seat[data-seat="${utg}"]`).addClass('is-str');
    }
}

function updateSeatDisplay(player) {
    const seat = player.seat_number;
    const $seat = $(`.poker-seat[data-seat="${seat}"]`);

    $seat.find('.empty-seat').addClass('hidden');
    $seat.find('.player-info').removeClass('hidden');

    const playerName = player.name || `Player ${seat}`;
    $seat.find('.player-name').text(playerName);

    // Track the persistent player_id (if named) so we can load notes later
    $seat.attr('data-player-id', player.player_id || '');

    if (playerName.startsWith('Player ')) {
        $seat.addClass('placeholder-player');
    } else {
        $seat.removeClass('placeholder-player');
    }

    const sessionVpip = player.session_hands > 0
        ? Math.round((player.session_vpip / player.session_hands) * 100)
        : 0;
    const sessionPfr = player.session_hands > 0
        ? Math.round((player.session_pfr / player.session_hands) * 100)
        : 0;

    $seat.find('.session-vpip').text(sessionVpip + '%');
    $seat.find('.session-pfr').text(sessionPfr + '%');

    if (player.total_hands && player.total_hands > 0) {
        const overallVpip = Math.round((player.total_vpip / player.total_hands) * 100);
        const overallPfr = Math.round((player.total_pfr / player.total_hands) * 100);

        $seat.find('.overall-vpip').text(overallVpip + '%');
        $seat.find('.overall-pfr').text(overallPfr + '%');
        $seat.find('.player-overall').removeClass('hidden');
    } else {
        $seat.find('.player-overall').addClass('hidden');
    }

    if (player.sitting_out) {
        $seat.find('.sitting-out-indicator').removeClass('hidden');
        $seat.addClass('sitting-out');
    } else {
        $seat.find('.sitting-out-indicator').addClass('hidden');
        $seat.removeClass('sitting-out');
    }

    // Hero ("this is me") marker
    if (player.is_hero) {
        $seat.addClass('is-hero');
    } else {
        $seat.removeClass('is-hero');
    }
}

function clearSeatDisplay(seat) {
    const $seat = $(`.poker-seat[data-seat="${seat}"]`);
    $seat.find('.empty-seat').removeClass('hidden');
    $seat.find('.player-info').addClass('hidden');
    $seat.find('.sitting-out-indicator').addClass('hidden');
    $seat.removeClass('sitting-out placeholder-player is-sb is-bb is-str is-hero');
    $seat.attr('data-player-id', '');
}

function handleSeatClick(seat) {
    // During an active hand, seat taps are reserved for the action overlay.
    if (activeHandState) return;

    const $seat = $(`.poker-seat[data-seat="${seat}"]`);
    const isEmpty = $seat.find('.empty-seat').is(':visible');

    if (switchingSeats) {
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
            <div class="text-sm text-gray-600">Or select an existing player:</div>
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

    const nameLabel = isPlaceholder ? 'Name this player' : 'Name / Update notes';
    const isHero = $seat.hasClass('is-hero');
    const heroLabel = isHero ? 'This is my seat ✓' : 'This is me';

    const modalContent = `
        <div class="space-y-3">
            <button class="btn ${isHero ? 'btn-secondary' : 'btn-primary'} w-full" data-action="hero">${heroLabel}</button>
            <button class="btn btn-secondary w-full" data-action="name">${nameLabel}</button>
            <button class="btn btn-success w-full" data-action="swap">Swap in new player</button>
            <button class="btn btn-secondary w-full" data-action="switch">Switch Seats</button>
            <button class="btn btn-secondary w-full" data-action="sitting-out">Toggle Sitting Out</button>
            <button class="btn btn-error w-full" data-action="remove">Player left / Remove</button>
            <button class="btn btn-secondary w-full" data-action="cancel">Cancel</button>
        </div>
    `;

    $('#modal-content').html(modalContent);
    $('#player-modal').removeClass('hidden');

    $('#modal-content button').on('click', function() {
        const action = $(this).data('action');

        switch(action) {
            case 'hero':
                closeModal();
                showNamePlayerModal(seat, true);
                break;
            case 'name':
                closeModal();
                showNamePlayerModal(seat);
                break;
            case 'swap':
                closeModal();
                swapPlayer(seat);
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

// Archive the current occupant (server preserves their stint if they played),
// then immediately open the add-player flow for the now-empty seat.
function swapPlayer(seat) {
    $.post('/poker/remove_player', {
        session_id: sessionState.session_id,
        seat_number: seat
    })
    .done(function(response) {
        if (response.success) {
            clearSeatDisplay(seat);
            refreshSessionState();
            showAddPlayerModal(seat);
        }
    });
}

function showNamePlayerModal(seat, hero = false) {
    const $seat = $(`.poker-seat[data-seat="${seat}"]`);
    const currentName = $seat.find('.player-name').text();
    const isPlaceholder = currentName.startsWith('Player ');

    // In hero mode, default the name to the saved hero name (so repeat sessions
    // are one tap) unless this seat already has a real name.
    let defaultName = currentName;
    if (hero && isPlaceholder && sessionState.hero_name) {
        defaultName = sessionState.hero_name;
    }

    const title = hero ? 'This is you' : 'Player';
    const nameLabel = hero ? 'Your name *' : 'Player Name *';

    const modalContent = `
        <div class="space-y-4">
            ${hero ? '<p class="text-sm text-gray-600">Marking this seat as you. Your stats will be tracked like any player.</p>' : ''}
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-2">${nameLabel}</label>
                <input type="text" id="player-name-input" class="w-full px-3 py-2 border border-gray-300 rounded-md" value="${defaultName}">
            </div>
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-2">Notes (Optional)</label>
                <textarea id="player-notes-input" class="w-full px-3 py-2 border border-gray-300 rounded-md" rows="3" placeholder="Player tendencies, observations..."></textarea>
            </div>
            <div class="flex gap-2">
                <button id="save-player-btn" class="btn btn-primary flex-1">${hero ? "That's me" : 'Save'}</button>
                <button id="close-modal-btn" class="btn btn-secondary flex-1">Cancel</button>
            </div>
        </div>
    `;

    $('#modal-content').html(modalContent);
    $('#player-modal').removeClass('hidden');

    // If this seat is a tracked player, load their saved notes so they're
    // viewable/editable right here mid-session.
    const playerId = $seat.attr('data-player-id');
    if (playerId) {
        $('#player-notes-input').attr('placeholder', 'Loading notes…');
        $.get('/poker/player_detail/' + playerId)
            .done(function(resp) {
                if (resp.success) {
                    $('#player-notes-input').val(resp.player.notes).attr('placeholder', 'Player tendencies, observations...');
                } else {
                    $('#player-notes-input').attr('placeholder', 'Player tendencies, observations...');
                }
            })
            .fail(function() {
                $('#player-notes-input').attr('placeholder', 'Player tendencies, observations...');
            });
    }

    $('#save-player-btn').on('click', function() {
        const name = $('#player-name-input').val().trim();
        const notes = $('#player-notes-input').val().trim();
        namePlayer(seat, name, notes, hero);
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
    if (!confirm('Remove this player from the seat? If they have played hands this session, their stats are saved to history first.')) return;

    $.post('/poker/remove_player', {
        session_id: sessionState.session_id,
        seat_number: seat
    })
    .done(function(response) {
        if (response.success) {
            clearSeatDisplay(seat);
            refreshSessionState();
        }
    });
}

function namePlayer(seat, name, notes, hero = false) {
    if (!name) {
        showToast('Player name is required', 'error');
        return;
    }

    $.post('/poker/name_player', {
        session_id: sessionState.session_id,
        seat_number: seat,
        player_name: name,
        player_notes: notes,
        is_hero: hero ? 1 : 0
    })
    .done(function(response) {
        if (response.success) {
            if (hero) sessionState.hero_name = name;
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

// --- Hand recording flow ---

function startHand() {
    if (!cachedActivePlayers || cachedActivePlayers.length < 2) {
        showToast('Need at least 2 active players', 'error');
        return;
    }

    const btnStraddle = $('#btn-straddle-toggle').is(':checked') ? 1 : 0;
    const utgStraddle = $('#utg-straddle-toggle').is(':checked') ? 1 : 0;

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
            updateActionQueue();
        }
    });
}

function recordAction(seat, action) {
    if (!seat || !activeHandState) {
        showToast('Start a hand first', 'error');
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
            paintSeatAction(seat, action);
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
            hideAllOverlays();
            $('#hand-count').text(response.hand_count);
            $('#felt-hand-num').text(response.hand_count + 1);
            updateButtonPosition(response.new_button_position);
            sessionState.button_position = response.new_button_position;
            activeHandState = null;
            showStraddle();

            $('#btn-straddle-toggle, #utg-straddle-toggle').prop('checked', false);

            refreshSessionState();
        }
    });
}

function skipHand(confirmFirst = true) {
    // Mid-hand "Misdeal" confirms (it discards a hand you've been recording);
    // the ready-state "Skip" just advances the button, so it skips the prompt.
    if (confirmFirst && !confirm('Discard this hand? The button moves but no stats are recorded.')) return;

    $.post('/poker/skip_hand', {
        session_id: sessionState.session_id
    })
    .done(function(response) {
        if (response.success) {
            $('.poker-seat').removeClass('action-fold action-raise action-call');
            hideAllOverlays();
            updateButtonPosition(response.new_button_position);
            sessionState.button_position = response.new_button_position;
            $('#felt-hand-num').text(parseInt($('#hand-count').text() || '0', 10) + 1);
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
                activeHandState.actions.pop();
                repaintActionColors(activeHandState.actions);
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
            setTimeout(() => location.reload(), 1200);
        }
    });
}

// --- Mode + overlay helpers ---

function showStraddle() {
    $('#hand-setup').removeClass('hidden');
    $('#hand-active').addClass('hidden');
    $('.felt-center').removeClass('hidden');
    hideAllOverlays();
}

function showActing() {
    $('#hand-setup').addClass('hidden');
    $('#hand-active').removeClass('hidden');
    $('.felt-center').addClass('hidden');
    $('#center-action').removeClass('hidden');
    if (activeHandState) $('#active-hand-num').text(activeHandState.hand_number);
}

// Hide the fixed centre action panel (and restore the hand-number display).
function hideAllOverlays() {
    $('#center-action').addClass('hidden');
}

// Point the fixed centre panel at the current player and set the Call/Check label.
function updateCenterAction(seat, isCheck) {
    $('#ca-player').text(seatLabel(seat));
    const $call = $('#center-action [data-action="call"], #center-action [data-action="check"]');
    if (isCheck) {
        $call.text('Check').attr('data-action', 'check');
    } else {
        $call.text('Call').attr('data-action', 'call');
    }
    $('#center-action').removeClass('hidden');
}

function paintSeatAction(seat, action) {
    const $seat = $(`.poker-seat[data-seat="${seat}"]`);
    $seat.removeClass('action-fold action-raise action-call active-action');
    if (action === 'fold') $seat.addClass('action-fold');
    else if (action === 'raise') $seat.addClass('action-raise');
    else if (action === 'call' || action === 'check') $seat.addClass('action-call');
    // 'skip' leaves the seat unmarked
}

function repaintActionColors(actions) {
    $('.poker-seat').removeClass('action-fold action-raise action-call');
    actions.forEach(a => paintSeatAction(a.seat, a.action));
}

// --- Action-order engine (unchanged logic) ---

function getNextActiveSeat(currentSeat, activePlayers) {
    for (let i = 1; i <= 9; i++) {
        const candidate = ((currentSeat - 1 + i) % 9) + 1;
        if (activePlayers.includes(candidate)) {
            return candidate;
        }
    }
    return null;
}

function getLastOptionSeat(buttonPos, activePlayers, hasBtnStraddle, hasUtgStraddle) {
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
    let firstSeat;
    if (hasBtnStraddle) {
        firstSeat = getNextActiveSeat(buttonPos, activePlayers);
    } else if (hasUtgStraddle) {
        const sb = getNextActiveSeat(buttonPos, activePlayers);
        const bb = getNextActiveSeat(sb, activePlayers);
        const utg = getNextActiveSeat(bb, activePlayers);
        firstSeat = getNextActiveSeat(utg, activePlayers);
    } else {
        const sb = getNextActiveSeat(buttonPos, activePlayers);
        const bb = getNextActiveSeat(sb, activePlayers);
        firstSeat = getNextActiveSeat(bb, activePlayers);
    }

    const order = [firstSeat];
    let seat = firstSeat;
    for (let i = 0; i < activePlayers.length - 1; i++) {
        seat = getNextActiveSeat(seat, activePlayers);
        order.push(seat);
    }
    return order;
}

function seatLabel(seat) {
    const name = $(`.poker-seat[data-seat="${seat}"] .player-name`).text() || `Player ${seat}`;
    return `Seat ${seat} (${name})`;
}

function updateActionQueue() {
    // Pre-hand: preview who acts first, no overlay yet
    if (!activeHandState) {
        hideAllOverlays();
        if (!sessionState || !cachedActivePlayers || cachedActivePlayers.length < 2) {
            currentActionSeat = null;
            $('.poker-seat').removeClass('active-action');
            $('#first-to-act').text('-');
            $('#felt-status').text('Add at least 2 players');
            return;
        }
        const btnStraddle = $('#btn-straddle-toggle').is(':checked');
        const utgStraddle = $('#utg-straddle-toggle').is(':checked');
        const order = buildActionOrder(sessionState.button_position, cachedActivePlayers, btnStraddle, utgStraddle);
        currentActionSeat = order[0] || null;
        $('.poker-seat').removeClass('active-action');
        if (currentActionSeat) {
            $(`.poker-seat[data-seat="${currentActionSeat}"]`).addClass('active-action');
            $('#first-to-act').text(seatLabel(currentActionSeat));
        }
        $('#felt-status').text('Ready — press Start Hand');
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

    const foldedSeats = new Set();
    let lastRaiseIndex = -1;
    const skippedSeats = new Set();

    for (let i = 0; i < actions.length; i++) {
        const a = actions[i];
        if (a.action === 'fold') foldedSeats.add(a.seat);
        if (a.action === 'raise') lastRaiseIndex = i;
        if (a.action === 'skip') skippedSeats.add(a.seat);
    }

    const remaining = actionOrder.filter(s => !foldedSeats.has(s) && !skippedSeats.has(s));

    if (remaining.length <= 1) {
        $('.poker-seat').removeClass('active-action');
        hideAllOverlays();
        currentActionSeat = null;
        completeHand();
        return;
    }

    let nextSeat = null;

    if (lastRaiseIndex === -1) {
        const actedSeats = new Set(actions.map(a => a.seat));
        for (const seat of actionOrder) {
            if (!foldedSeats.has(seat) && !skippedSeats.has(seat) && !actedSeats.has(seat)) {
                nextSeat = seat;
                break;
            }
        }
    } else {
        const lastRaiserSeat = actions[lastRaiseIndex].seat;
        const actedAfterRaise = new Set();
        for (let i = lastRaiseIndex + 1; i < actions.length; i++) {
            actedAfterRaise.add(actions[i].seat);
        }

        const raiserIdx = actionOrder.indexOf(lastRaiserSeat);
        for (let i = 1; i < actionOrder.length; i++) {
            const seat = actionOrder[(raiserIdx + i) % actionOrder.length];
            if (seat === lastRaiserSeat) continue;
            if (foldedSeats.has(seat) || skippedSeats.has(seat)) continue;
            if (!actedAfterRaise.has(seat)) {
                nextSeat = seat;
                break;
            }
        }
    }

    if (nextSeat) {
        currentActionSeat = nextSeat;
        $('#current-action-player').text(seatLabel(currentActionSeat));
        $('#felt-status').text('Recording…');

        $('.poker-seat').removeClass('active-action');
        $(`.poker-seat[data-seat="${currentActionSeat}"]`).addClass('active-action');

        const lastOptionSeat = getLastOptionSeat(
            buttonPos, activePlayers,
            activeHandState.has_btn_straddle, activeHandState.has_utg_straddle
        );
        const isCheck = (nextSeat === lastOptionSeat && lastRaiseIndex === -1);
        updateCenterAction(currentActionSeat, isCheck);
    } else {
        $('.poker-seat').removeClass('active-action');
        hideAllOverlays();
        currentActionSeat = null;
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
