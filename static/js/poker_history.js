// Poker History — sessions log + player directory with notes

$(document).ready(function() {
    setupTabs();
    setupSessionAccordion();
    setupPlayerDirectory();
});

function escapeHtml(str) {
    return $('<div>').text(str == null ? '' : str).html();
}

// --- Tabs ---
function setupTabs() {
    $('.ph-tab').on('click', function() {
        const tab = $(this).data('tab');
        $('.ph-tab').removeClass('btn-primary').addClass('btn-secondary');
        $(this).removeClass('btn-secondary').addClass('btn-primary');
        $('.ph-panel').addClass('hidden');
        $('#tab-' + tab).removeClass('hidden');
    });
}

// --- Sessions accordion (lazy-loaded detail) ---
function setupSessionAccordion() {
    $('.ph-session-head').on('click', function() {
        const $session = $(this).closest('.ph-session');
        const $body = $session.find('.ph-session-body');
        const $caret = $session.find('.ph-caret');
        const sessionId = $session.data('session-id');

        if (!$body.hasClass('hidden')) {
            $body.addClass('hidden');
            $caret.html('&#9656;'); // ►
            return;
        }

        $caret.html('&#9662;'); // ▼
        $body.removeClass('hidden');

        if (!$body.data('loaded')) {
            $body.html('<p class="text-sm text-gray-400">Loading…</p>');
            $.get('/poker/session_detail/' + sessionId)
                .done(function(resp) {
                    if (resp.success) {
                        $body.html(renderSessionDetail(resp.players));
                        $body.data('loaded', true);
                        wireUnnamedToggle($body);
                    } else {
                        $body.html('<p class="text-sm text-red-500">Could not load session.</p>');
                    }
                })
                .fail(function() {
                    $body.html('<p class="text-sm text-red-500">Could not load session.</p>');
                });
        }
    });
}

function statRow(p, greyed) {
    const cls = greyed ? 'text-gray-400' : 'text-gray-800';
    const dur = p.duration ? `<span class="block text-xs text-gray-400">${escapeHtml(p.duration)} at table</span>` : '';
    return `
        <div class="flex items-center py-1.5 text-sm ${cls}">
            <span class="pr-2 flex-1 min-w-0">
                <span class="block truncate">${escapeHtml(p.name)}</span>
                ${dur}
            </span>
            <span class="flex tabular-nums text-right">
                <span class="w-10">${p.hands}</span>
                <span class="w-12"><b>${p.vpip}%</b></span>
                <span class="w-12"><b>${p.pfr}%</b></span>
            </span>
        </div>`;
}

function renderSessionDetail(players) {
    const named = players.filter(p => p.is_named).sort((a, b) => b.vpip - a.vpip);
    const unnamed = players.filter(p => !p.is_named).sort((a, b) => a.seat - b.seat);

    let html = `
        <div class="flex items-center text-xs text-gray-400 uppercase tracking-wide border-b border-gray-100 pb-1 mb-1">
            <span class="flex-1">Player</span>
            <span class="flex text-right">
                <span class="w-10">Hnds</span><span class="w-12">VPIP</span><span class="w-12">PFR</span>
            </span>
        </div>`;

    if (named.length === 0) {
        html += '<p class="text-sm text-gray-400 py-2">No tracked players this session.</p>';
    } else {
        html += named.map(p => statRow(p, false)).join('');
    }

    if (unnamed.length > 0) {
        html += `
            <button class="ph-unnamed-toggle text-xs text-blue-600 mt-3">Show ${unnamed.length} unnamed seat${unnamed.length === 1 ? '' : 's'}</button>
            <div class="ph-unnamed hidden mt-1 border-t border-gray-100 pt-1">
                ${unnamed.map(p => statRow(p, true)).join('')}
            </div>`;
    }
    return html;
}

function wireUnnamedToggle($scope) {
    $scope.find('.ph-unnamed-toggle').on('click', function() {
        const $list = $scope.find('.ph-unnamed');
        const hidden = $list.hasClass('hidden');
        $list.toggleClass('hidden');
        const n = $list.children().length;
        $(this).text(hidden ? 'Hide unnamed seats' : `Show ${n} unnamed seat${n === 1 ? '' : 's'}`);
    });
}

// --- Player directory + notes ---
function setupPlayerDirectory() {
    $('.ph-player').on('click', function() {
        const playerId = $(this).data('player-id');
        openPlayerDetail(playerId);
    });
}

function openPlayerDetail(playerId) {
    $('#player-detail-content').html('<p class="text-sm text-gray-400">Loading…</p>');
    $('#player-detail-modal').removeClass('hidden');

    $.get('/poker/player_detail/' + playerId)
        .done(function(resp) {
            if (!resp.success) {
                $('#player-detail-content').html('<p class="text-sm text-red-500">Could not load player.</p>');
                return;
            }
            renderPlayerDetail(resp.player, resp.appearances, resp.preflop);
        })
        .fail(function() {
            $('#player-detail-content').html('<p class="text-sm text-red-500">Could not load player.</p>');
        });
}

function preflopPanel(pf) {
    if (!pf || pf.hands === 0) {
        return `<div class="mt-4">
            <div class="text-sm font-semibold text-gray-700 mb-1">Preflop reads</div>
            <p class="text-sm text-gray-400">No tracked hands yet. These build up as you log hands from now on.</p>
        </div>`;
    }
    return `
        <div class="mt-4">
            <div class="flex items-baseline justify-between mb-1">
                <div class="text-sm font-semibold text-gray-700">Preflop reads</div>
                <div class="text-xs text-gray-400">${pf.hands} tracked hand${pf.hands === 1 ? '' : 's'}</div>
            </div>
            <div class="grid grid-cols-3 gap-2 text-center mb-2">
                <div class="bg-gray-50 rounded-md py-1.5"><div class="font-bold text-primary">${pf.vpip}%</div><div class="text-xs text-gray-500">VPIP</div></div>
                <div class="bg-gray-50 rounded-md py-1.5"><div class="font-bold text-primary">${pf.pfr}%</div><div class="text-xs text-gray-500">PFR</div></div>
                <div class="bg-gray-50 rounded-md py-1.5"><div class="font-bold text-primary">${pf.limp}%</div><div class="text-xs text-gray-500">Limp</div></div>
            </div>
            <div class="text-sm text-gray-700 space-y-0.5">
                <div class="flex justify-between"><span>3-Bet</span><span class="tabular-nums"><b>${pf.three_bet_pct}%</b> <span class="text-gray-400">(${pf.three_bet_ct} of ${pf.three_bet_opp} spots)</span></span></div>
                <div class="flex justify-between"><span>Limp &rarr; Call</span><span class="tabular-nums">${pf.limp_call_ct} <span class="text-gray-400">(${pf.limp_call_pct}% of limps)</span></span></div>
                <div class="flex justify-between"><span>Limp &rarr; Re-raise</span><span class="tabular-nums">${pf.limp_rr_ct} <span class="text-gray-400">(${pf.limp_rr_pct}% of limps)</span></span></div>
            </div>
        </div>`;
}

function renderPlayerDetail(player, appearances, preflop) {
    let appearHtml = '';
    if (appearances.length === 0) {
        appearHtml = '<p class="text-sm text-gray-400">No completed sessions yet.</p>';
    } else {
        appearHtml = appearances.map(a => `
            <div class="flex items-center justify-between py-1 text-sm text-gray-700">
                <span>${escapeHtml(a.date)}${a.duration ? ' · <span class="text-gray-400">' + escapeHtml(a.duration) + '</span>' : ''}</span>
                <span class="flex gap-3 tabular-nums">
                    <span>${a.hands}h</span><span>${a.vpip}% V</span><span>${a.pfr}% P</span>
                </span>
            </div>`).join('');
    }

    const html = `
        <div class="flex justify-between items-start mb-3">
            <h3 class="text-xl font-bold text-gray-900">${escapeHtml(player.name)}</h3>
            <button id="pd-close" class="text-gray-400 text-2xl leading-none">&times;</button>
        </div>
        <div class="grid grid-cols-3 gap-2 text-center mb-4">
            <div class="bg-gray-50 rounded-md py-2">
                <div class="text-lg font-bold text-primary">${player.vpip}%</div>
                <div class="text-xs text-gray-500">VPIP</div>
            </div>
            <div class="bg-gray-50 rounded-md py-2">
                <div class="text-lg font-bold text-primary">${player.pfr}%</div>
                <div class="text-xs text-gray-500">PFR</div>
            </div>
            <div class="bg-gray-50 rounded-md py-2">
                <div class="text-lg font-bold text-gray-800">${player.total_hands}</div>
                <div class="text-xs text-gray-500">Hands</div>
            </div>
        </div>
        <label class="block text-sm font-medium text-gray-700 mb-1">Notes</label>
        <textarea id="pd-notes" class="w-full px-3 py-2 border border-gray-300 rounded-md" rows="4"
                  placeholder="Tendencies, tells, sizing reads…"></textarea>
        <button id="pd-save" class="btn btn-primary w-full mt-2" data-player-id="${player.id}">Save Notes</button>
        ${preflopPanel(preflop)}
        <div class="mt-4">
            <div class="text-sm font-semibold text-gray-700 mb-1">Sessions played</div>
            ${appearHtml}
        </div>
    `;
    $('#player-detail-content').html(html);
    $('#pd-notes').val(player.notes);

    $('#pd-close').on('click', () => $('#player-detail-modal').addClass('hidden'));
    $('#pd-save').on('click', function() {
        savePlayerNotes(player.id, $('#pd-notes').val());
    });
}

function savePlayerNotes(playerId, notes) {
    $.post('/poker/update_player_notes', { player_id: playerId, notes: notes })
        .done(function(resp) {
            if (resp.success) {
                $('#player-detail-modal').addClass('hidden');
            }
        });
}
