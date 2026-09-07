
        // Telegram WebApp Setup
        const tg = window.Telegram ? window.Telegram.WebApp : null;
        if (tg) {
            tg.expand();
            tg.ready();
        }

        const currentTgId = 0;
        let currentHeroData = null;

        // Trigger Haptics safely
        function triggerHaptic(type) {
            if (tg && tg.HapticFeedback) {
                if (type === 'impact') tg.HapticFeedback.impactOccurred('medium');
                else if (type === 'success') tg.HapticFeedback.notificationOccurred('success');
                else if (type === 'error') tg.HapticFeedback.notificationOccurred('error');
            }
        }

        // Toast Notification System
        function showToast(msg, type = 'success') {
            const container = document.getElementById('toastContainer');
            if (!container) return;

            const toast = document.createElement('div');
            toast.className = `toast ${type}`;
            const icon = type === 'success' ? '✅' : '⚠️';
            toast.innerHTML = `<span>${icon}</span><span>${msg}</span>`;

            container.appendChild(toast);
            triggerHaptic(type === 'success' ? 'success' : 'error');

            setTimeout(() => {
                toast.style.transition = 'all 0.3s ease';
                toast.style.opacity = '0';
                toast.style.transform = 'translateY(-10px)';
                setTimeout(() => toast.remove(), 300);
            }, 3000);
        }

        // Main Tab Switcher
        function switchMainTab(tabName, el) {
            triggerHaptic('impact');
            document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));

            const target = document.getElementById('tab' + tabName.charAt(0).toUpperCase() + tabName.slice(1));
            if (target) target.classList.add('active');
            if (el) el.classList.add('active');

            if (tabName === 'profile') loadHeroData();
        }

        // Shop Category Filter
        function filterShopCategory(cat, el) {
            triggerHaptic('impact');
            document.querySelectorAll('#tabShop .filter-chip').forEach(c => c.classList.remove('active'));
            if (el) el.classList.add('active');

            const items = document.querySelectorAll('#shopItemsGrid .shop-card');
            items.forEach(card => {
                const itemCat = card.getAttribute('data-shop-cat');
                if (cat === 'all' || itemCat === cat) {
                    card.style.display = 'flex';
                } else {
                    card.style.display = 'none';
                }
            });
        }

        // Roles Filter
        function setRoleCategory(cat, el) {
            triggerHaptic('impact');
            document.querySelectorAll('#tabRoles .filter-chip').forEach(c => c.classList.remove('active'));
            if (el) el.classList.add('active');

            const cards = document.querySelectorAll('#rolesGrid .role-card');
            cards.forEach(card => {
                const roleCat = card.getAttribute('data-category');
                if (cat === 'all' || roleCat === cat) {
                    card.style.display = 'block';
                } else {
                    card.style.display = 'none';
                }
            });
        }

        function filterRoles() {
            const query = (document.getElementById('roleSearchInput').value || '').toLowerCase().trim();
            const cards = document.querySelectorAll('#rolesGrid .role-card');
            cards.forEach(card => {
                const name = card.getAttribute('data-name') || '';
                const desc = card.getAttribute('data-desc') || '';
                if (!query || name.includes(query) || desc.includes(query)) {
                    card.style.display = 'block';
                } else {
                    card.style.display = 'none';
                }
            });
        }

        // ===================================================================
        // 🥷 GEROY SYSTEM
        // ===================================================================
        async function loadHeroData() {
            try {
                const res = await fetch(`/webapp/api/hero/details/?tg_id=${currentTgId}`);
                const d = await res.json();
                if (d.ok && d.hero) {
                    currentHeroData = d.hero;
                    const nameEl = document.getElementById('heroCardName');
                    const levelEl = document.getElementById('heroCardLevel');
                    const chargesEl = document.getElementById('heroCardCharges');
                    const scoreEl = document.getElementById('heroCardScore');
                    const tagEl = document.getElementById('heroCardStatusTag');

                    if (nameEl) nameEl.innerText = d.hero.name;
                    if (levelEl) levelEl.innerText = `${d.hero.level}-Daraja (${d.hero.min_damage_percent}%-${d.hero.max_damage_percent}% otish)`;
                    if (chargesEl) chargesEl.innerText = `${d.hero.charges} / 10`;
                    if (scoreEl) scoreEl.innerText = `${d.hero.score} Ball`;

                    if (tagEl) {
                        tagEl.innerText = d.hero.is_active ? "Faol" : "O'chirilgan";
                        tagEl.className = `hero-status-tag ${d.hero.is_active ? '' : 'inactive'}`;
                    }
                }
            } catch (e) {}
        }

        async function buyHeroPrompt() {
            const name = prompt("Yangi Geroyingiz uchun nom kiriting:", "Kobra");
            if (!name || !name.trim()) return;

            try {
                const res = await fetch('/webapp/api/hero/create/', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ tg_id: currentTgId, name: name.trim() })
                });
                const d = await res.json();
                if (d.ok) {
                    showToast(d.message, "success");
                    await loadHeroData();
                } else {
                    showToast(d.error || "Xatolik yuz berdi", "error");
                }
            } catch (e) {
                showToast("Server bilan aloqa xatosi", "error");
            }
        }

        async function rechargeHeroAction() {
            try {
                const res = await fetch('/webapp/api/hero/recharge/', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ tg_id: currentTgId })
                });
                const d = await res.json();
                if (d.ok) {
                    showToast(d.message, "success");
                    await loadHeroData();
                } else {
                    showToast(d.error || "Xatolik", "error");
                }
            } catch (e) {
                showToast("Server bilan aloqa xatosi", "error");
            }
        }

        async function renameHeroPrompt() {
            const newName = prompt("Geroyingiz uchun yangi nom kiriting:", currentHeroData ? currentHeroData.name : "");
            if (!newName || newName.trim().length < 2) return;

            try {
                const res = await fetch('/webapp/api/hero/rename/', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ tg_id: currentTgId, name: newName.trim() })
                });
                const d = await res.json();
                if (d.ok) {
                    showToast(d.message, "success");
                    await loadHeroData();
                } else {
                    showToast(d.error || "Xatolik", "error");
                }
            } catch (e) {
                showToast("Server bilan aloqa xatosi", "error");
            }
        }

        async function transferHeroPrompt() {
            const recipient = prompt("Geroyni qabul qiluvchining Telegram ID yoki @username ini kiriting:");
            if (!recipient || !recipient.trim()) return;

            try {
                const res = await fetch('/webapp/api/hero/transfer/', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ sender_tg_id: currentTgId, recipient: recipient.trim() })
                });
                const d = await res.json();
                if (d.ok) {
                    showToast(d.message, "success");
                    await loadHeroData();
                } else {
                    showToast(d.error || "Xatolik", "error");
                }
            } catch (e) {
                showToast("Server bilan aloqa xatosi", "error");
            }
        }

        async function buyItem(itemCode) {
            try {
                const res = await fetch('/webapp/api/shop/buy/', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ tg_id: currentTgId, item_code: itemCode })
                });
                const d = await res.json();
                if (d.ok) {
                    showToast(d.message || "Xarid amalga oshirildi!", "success");
                    if (d.new_money) {
                        const mEl = document.getElementById('userMoney');
                        const topM = document.getElementById('topMoneyVal');
                        if (mEl) mEl.innerText = `$ ${d.new_money}`;
                        if (topM) topM.innerText = d.new_money;
                    }
                    if (d.new_diamonds !== undefined) {
                        const diaEl = document.getElementById('userDiamonds');
                        const topDia = document.getElementById('topDiaVal');
                        if (diaEl) diaEl.innerText = `💎 ${d.new_diamonds}`;
                        if (topDia) topDia.innerText = d.new_diamonds;
                    }
                } else {
                    showToast(d.error || "Xatolik yuz berdi", "error");
                }
            } catch (e) {
                showToast("Xaridda xatolik yuz berdi", "error");
            }
        }

        // ===================================================================
        // 🎰 CYBERPUNK ROULETTE & CHEST LOGIC
        // ===================================================================
        const ROULETTE_NUMBERS = [
            { num: 0, col: 'green' },
            { num: 32, col: 'red' }, { num: 15, col: 'black' }, { num: 19, col: 'red' },
            { num: 4, col: 'black' }, { num: 21, col: 'red' }, { num: 2, col: 'black' },
            { num: 25, col: 'red' }, { num: 17, col: 'black' }, { num: 34, col: 'red' },
            { num: 6, col: 'black' }, { num: 27, col: 'red' }, { num: 13, col: 'black' },
            { num: 36, col: 'red' }, { num: 11, col: 'black' }, { num: 30, col: 'red' },
            { num: 8, col: 'black' }, { num: 23, col: 'red' }, { num: 10, col: 'black' },
            { num: 5, col: 'red' }, { num: 24, col: 'black' }, { num: 16, col: 'red' },
            { num: 33, col: 'black' }, { num: 1, col: 'red' }, { num: 20, col: 'black' },
            { num: 14, col: 'red' }, { num: 31, col: 'black' }, { num: 9, col: 'red' },
            { num: 22, col: 'black' }, { num: 18, col: 'red' }, { num: 29, col: 'black' },
            { num: 7, col: 'red' }, { num: 28, col: 'black' }, { num: 12, col: 'red' },
            { num: 35, col: 'black' }, { num: 3, col: 'red' }, { num: 26, col: 'black' }
        ];

        let isRouletteSpinning = false;

        function initRouletteTrack() {
            const track = document.getElementById('rouletteTrack');
            if (!track) return;

            let itemsHtml = '';
            for (let rep = 0; rep < 5; rep++) {
                ROULETTE_NUMBERS.forEach(item => {
                    itemsHtml += `
                        <div class="r-tile ${item.col}" data-num="${item.num}">
                            <span>${item.num}</span>
                            <span class="r-tile-sub">${item.col === 'green' ? 'Zero' : item.col}</span>
                        </div>
                    `;
                });
            }
            track.innerHTML = itemsHtml;
        }

        function switchCasinoSub(sub, el) {
            triggerHaptic('impact');
            document.querySelectorAll('#tabCasino .filter-chip').forEach(c => c.classList.remove('active'));
            if (el) el.classList.add('active');

            const rSec = document.getElementById('casinoRouletteSection');
            const cSec = document.getElementById('casinoChestsSection');

            if (sub === 'roulette') {
                if (rSec) rSec.style.display = 'block';
                if (cSec) cSec.style.display = 'none';
            } else {
                if (rSec) rSec.style.display = 'none';
                if (cSec) cSec.style.display = 'block';
            }
        }

        function setRouletteBet(val) {
            triggerHaptic('impact');
            const inp = document.getElementById('rouletteBetAmount');
            if (inp) inp.value = val;
        }

        function multiplyRouletteBet(mul) {
            triggerHaptic('impact');
            const inp = document.getElementById('rouletteBetAmount');
            if (inp) {
                let cur = parseInt(inp.value, 10) || 100;
                inp.value = Math.max(10, Math.floor(cur * mul));
            }
        }

        function setMaxRouletteBet() {
            triggerHaptic('impact');
            const mEl = document.getElementById('topMoneyVal');
            if (mEl) {
                const raw = parseInt(mEl.innerText.replace(/[^0-9]/g, ''), 10) || 1000;
                const inp = document.getElementById('rouletteBetAmount');
                if (inp) inp.value = Math.min(raw, 500000);
            }
        }

        async function spinRouletteAction(color) {
            if (isRouletteSpinning) return;

            const inp = document.getElementById('rouletteBetAmount');
            const bet = parseInt(inp ? inp.value : 100, 10);
            if (!bet || bet <= 0) {
                showToast("Tikish summasini kiriting!", "error");
                return;
            }

            isRouletteSpinning = true;
            triggerHaptic('impact');

            const resBox = document.getElementById('rouletteResultBox');
            if (resBox) resBox.innerHTML = '<span style="color: #38BDF8; font-weight: 800;">Aylanmoqda... 🎲</span>';

            try {
                const res = await fetch('/webapp/api/casino/roulette/spin/', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ tg_id: currentTgId, bet_amount: bet, bet_color: color })
                });
                const data = await res.json();

                if (!data.ok) {
                    isRouletteSpinning = false;
                    showToast(data.error || "Xatolik yuz berdi", "error");
                    if (resBox) resBox.innerText = "";
                    return;
                }

                const track = document.getElementById('rouletteTrack');
                const tileWidth = 72; // 64px width + 8px gap
                const targetIdx = ROULETTE_NUMBERS.findIndex(x => x.num === data.number);
                const landIndex = (ROULETTE_NUMBERS.length * 3) + (targetIdx >= 0 ? targetIdx : 0);

                const container = track.parentElement;
                const centerOffset = container.offsetWidth / 2 - 32;
                const targetTranslateX = -(landIndex * tileWidth - centerOffset);

                track.style.transition = 'transform 3.6s cubic-bezier(0.12, 0.8, 0.18, 1)';
                track.style.transform = `translateX(${targetTranslateX}px)`;

                // Add to recent history pills
                setTimeout(() => {
                    const histRow = document.getElementById('rouletteHistoryRow');
                    if (histRow) {
                        const p = document.createElement('div');
                        p.className = `roll-badge ${data.color}`;
                        p.innerText = data.number;
                        histRow.insertBefore(p, histRow.firstChild);
                        if (histRow.children.length > 10) histRow.removeChild(histRow.lastChild);
                    }
                }, 3400);

                setTimeout(() => {
                    isRouletteSpinning = false;
                    const moneyEl = document.getElementById('userMoney');
                    const topMoney = document.getElementById('topMoneyVal');
                    if (moneyEl) moneyEl.innerText = `$ ${data.new_money}`;
                    if (topMoney) topMoney.innerText = data.new_money;

                    if (resBox) {
                        if (data.won) {
                            resBox.innerHTML = `<span style="color: #10B981; font-size: 15px; font-weight: 900;">🎉 G'ALABA! +${data.payout.toLocaleString()} 💶 (Tushgan: ${data.number})</span>`;
                            showToast(data.message, "success");
                            triggerHaptic('success');
                        } else {
                            resBox.innerHTML = `<span style="color: #EF4444; font-size: 15px; font-weight: 800;">❌ Boy berildi. (Tushgan: ${data.number})</span>`;
                            showToast(data.message, "error");
                            triggerHaptic('error');
                        }
                    }
                }, 3700);

            } catch (e) {
                isRouletteSpinning = false;
                showToast("Server bilan aloqa xatosi", "error");
                if (resBox) resBox.innerText = "";
            }
        }

        async function openChestAction(type) {
            triggerHaptic('impact');
            try {
                const res = await fetch('/webapp/api/casino/chest/open/', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ tg_id: currentTgId, chest_type: type })
                });
                const data = await res.json();

                if (!data.ok) {
                    showToast(data.error || "Xatolik yuz berdi", "error");
                    return;
                }

                // Update balances
                const moneyEl = document.getElementById('userMoney');
                const topMoney = document.getElementById('topMoneyVal');
                if (moneyEl) moneyEl.innerText = `$ ${data.new_money}`;
                if (topMoney) topMoney.innerText = data.new_money;

                const diaEl = document.getElementById('userDiamonds');
                const topDia = document.getElementById('topDiaVal');
                if (diaEl) diaEl.innerText = `💎 ${data.new_diamonds}`;
                if (topDia) topDia.innerText = data.new_diamonds;

                // Open Reveal Modal
                const m = document.getElementById('chestModal');
                const iconEl = document.getElementById('chestModalIcon');
                const titleEl = document.getElementById('chestModalTitle');
                const descEl = document.getElementById('chestModalDesc');

                if (iconEl) iconEl.innerText = data.prize.icon || '🎁';
                if (titleEl) titleEl.innerText = data.prize.title;
                if (descEl) descEl.innerText = data.prize.desc;

                if (m) m.classList.add('active');
                showToast(data.message, "success");
                triggerHaptic('success');

            } catch (e) {
                showToast("Server bilan aloqa xatosi", "error");
            }
        }

        function closeChestModal() {
            triggerHaptic('impact');
            const m = document.getElementById('chestModal');
            if (m) m.classList.remove('active');
        }

        function closeChestModalOnOutside(e) {
            if (e.target.id === 'chestModal') closeChestModal();
        }

        function closeHeroModal() {
            triggerHaptic('impact');
            const m = document.getElementById('heroModal');
            if (m) m.classList.remove('active');
        }

        function closeHeroModalOnOutside(e) {
            if (e.target.id === 'heroModal') closeHeroModal();
        }

        function showNotificationCenter() {
            triggerHaptic('impact');
            showToast("Barcha bildirishnomalar o'qilgan! 🔔", "success");
        }

        async function openSelectedGroupCabinet() {
            triggerHaptic('impact');
            showToast("Guruh kabineti yuklanmoqda...", "success");
        }

        // Initialize on load
        document.addEventListener('DOMContentLoaded', function() {
            initRouletteTrack();
            loadHeroData();
        });
    