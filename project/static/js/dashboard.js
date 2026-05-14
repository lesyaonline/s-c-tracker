/**
 * S&C Tracker — Дашборд
 * Управление активами, график, настройки (валюта, тема)
 */

// ═══ Состояние ════════════════════════════════════════════════
let currency   = localStorage.getItem('sc_currency') || 'usd';
let chartDays  = 7;
let portfolio  = null;   // Chart.js экземпляр
let selected   = null;   // выбранный актив в модалке

// ═══ Инициализация ════════════════════════════════════════════
document.addEventListener('DOMContentLoaded', () => {
  applyTheme(localStorage.getItem('sc_theme') === 'dark');
  syncCurButtons();
  loadAll();
  setInterval(loadAll, 60_000);

  // Закрыть модалку по оверлею
  document.getElementById('modal').addEventListener('click', e => {
    if (e.target.id === 'modal') closeModal();
  });
  // Закрыть панель настроек при клике вне
  document.addEventListener('click', e => {
    const wrap = document.querySelector('.settings-wrap');
    if (wrap && !wrap.contains(e.target)) {
      document.getElementById('settingsPanel').classList.remove('open');
    }
  });
});

// ═══ Загрузка всего ═══════════════════════════════════════════
async function loadAll() {
  await Promise.all([loadStats(), loadAssets(), loadChart()]);
}

// ═══ Статистика (виджет баланса) ══════════════════════════════
async function loadStats() {
  const r = await fetch(`/api/portfolio/stats?currency=${currency}`);
  const s = await r.json();
  const sym = s.currency_symbol;
  const sign = v => v >= 0 ? '+' : '';

  document.getElementById('bwAmount').textContent =
    sym + fmt(s.total_current);
  document.getElementById('bwInvested').textContent =
    sym + fmt(s.total_investment);
  document.getElementById('bwProfit').textContent =
    sign(s.total_profit) + sym + fmt(Math.abs(s.total_profit));
  document.getElementById('bwPct').textContent =
    sign(s.profit_percent) + s.profit_percent.toFixed(2) + '%';

  const pctEl = document.getElementById('pillPct');
  const absEl = document.getElementById('pillAbs');
  pctEl.textContent = sign(s.profit_percent) + s.profit_percent.toFixed(2) + '%';
  absEl.textContent = sign(s.total_profit) + sym + fmt(Math.abs(s.total_profit));

  // Показываем курсы в подвале
  if (s.rates) {
    document.getElementById('rateUsd').textContent =
      `USD/RUB: ${s.rates.usd_rub.toFixed(2)}`;
    document.getElementById('rateCny').textContent =
      `CNY/RUB: ${s.rates.cny_rub.toFixed(2)}`;
  }
}

// ═══ Таблица активов ══════════════════════════════════════════
async function loadAssets() {
  const r = await fetch(`/api/assets?currency=${currency}`);
  const assets = await r.json();

  const sTbody = document.getElementById('stocksBody');
  const cTbody = document.getElementById('cryptoBody');
  sTbody.innerHTML = '';
  cTbody.innerHTML = '';

  let hasStocks = false, hasCrypto = false;

  assets.forEach(a => {
    const sym   = a.currency_symbol;
    const cls   = a.profit >= 0 ? 'pos' : 'neg';
    const sign  = a.profit >= 0 ? '+' : '';
    const badge = a.type === 'stock'
      ? '<span class="badge badge-s">Акция</span>'
      : '<span class="badge badge-c">Крипта</span>';

    // Количество: акции — целые, крипта — до 6 знаков
    const qtyFmt = a.type === 'stock'
      ? a.quantity.toFixed(0)
      : a.quantity.toLocaleString('ru-RU', { maximumFractionDigits: 6 });

    const row = `
      <tr>
        <td>
          <div class="a-name">${a.name}${badge}</div>
          <div class="a-sub">${a.code} · куплено ${a.purchase_date}</div>
        </td>
        <td>${qtyFmt}</td>
        <td>${sym}${fmt(a.purchase_price)}</td>
        <td>${sym}${fmt(a.current_price)}</td>
        <td>${sym}${fmt(a.invest_value)}</td>
        <td>${sym}${fmt(a.current_value)}</td>
        <td class="${cls}">${sign}${sym}${fmt(Math.abs(a.profit))}<br>
          <span style="font-size:11px;opacity:.8">${sign}${a.profit_percent.toFixed(2)}%</span>
        </td>
        <td>
          <button class="btn-del" onclick="deleteAsset(${a.id})">Удалить</button>
        </td>
      </tr>`;

    if (a.type === 'stock') { sTbody.innerHTML += row; hasStocks = true; }
    else                    { cTbody.innerHTML += row; hasCrypto = true; }
  });

  if (!hasStocks) sTbody.innerHTML =
    '<tr class="empty-row"><td colspan="8">Акций пока нет</td></tr>';
  if (!hasCrypto) cTbody.innerHTML =
    '<tr class="empty-row"><td colspan="8">Криптовалют пока нет</td></tr>';
}

// ═══ График ═══════════════════════════════════════════════════
async function loadChart() {
  const r = await fetch(`/api/portfolio/chart?days=${chartDays}&currency=${currency}`);
  const d = await r.json();

  const ctx = document.getElementById('portfolioChart').getContext('2d');
  if (portfolio) portfolio.destroy();

  const isUp = d.data.length > 1 && d.data[d.data.length - 1] >= d.data[0];
  const lineColor = isUp ? '#22c55e' : '#ef4444';
  const fillColor = isUp ? 'rgba(34,197,94,.1)' : 'rgba(239,68,68,.1)';

  portfolio = new Chart(ctx, {
    type: 'line',
    data: {
      labels: d.labels,
      datasets: [{
        label: 'Стоимость портфеля',
        data: d.data,
        borderColor: lineColor,
        backgroundColor: fillColor,
        fill: true,
        tension: 0.38,
        pointRadius: d.data.length > 30 ? 0 : 3,
        pointHoverRadius: 5,
        borderWidth: 2.5,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: ctx => {
              const sym = { usd: '$', rub: '₽', cny: '¥' }[currency] || '$';
              return sym + ctx.parsed.y.toLocaleString('ru-RU', { maximumFractionDigits: 2 });
            }
          }
        }
      },
      scales: {
        x: { ticks: { font: { size: 11 }, maxTicksLimit: 10 }, grid: { display: false } },
        y: {
          ticks: {
            font: { size: 11 },
            callback: v => {
              const sym = { usd: '$', rub: '₽', cny: '¥' }[currency] || '$';
              return sym + v.toLocaleString('ru-RU', { maximumFractionDigits: 0 });
            }
          },
          grid: { color: 'rgba(128,128,128,.08)' }
        }
      }
    }
  });
}

// ═══ Период графика ════════════════════════════════════════════
function setPeriod(days, btn) {
  chartDays = days;
  document.querySelectorAll('.p-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  loadChart();
}

// ═══ Удаление актива ══════════════════════════════════════════
async function deleteAsset(id) {
  if (!confirm('Удалить этот актив из портфеля?')) return;
  await fetch(`/api/assets/${id}`, { method: 'DELETE' });
  loadAll();
}

// ═══ Модальное окно ═══════════════════════════════════════════
function openModal() {
  selected = null;
  document.querySelectorAll('.asset-card').forEach(c => c.classList.remove('selected'));
  document.getElementById('addForm').style.display = 'none';
  document.getElementById('formError').style.display = 'none';
  document.getElementById('assetSearch').value = '';
  filterAssets();
  document.getElementById('modal').classList.add('active');
}
function closeModal() {
  document.getElementById('modal').classList.remove('active');
}

function filterAssets() {
  const q = document.getElementById('assetSearch').value.toLowerCase();
  document.querySelectorAll('.asset-card').forEach(c => {
    c.style.display = c.dataset.search.includes(q) ? '' : 'none';
  });
}

function selectAsset(type, code, name) {
  // Снять предыдущий выбор
  document.querySelectorAll('.asset-card').forEach(c => c.classList.remove('selected'));
  // Выделить нажатую карточку
  event.currentTarget.classList.add('selected');

  selected = { type, code, name };

  document.getElementById('selectedBanner').textContent = `Выбрано: ${name} (${code})`;
  document.getElementById('selType').value = type;
  document.getElementById('selCode').value = code;
  document.getElementById('selName').value = name;

  // Дефолтная дата — сегодня
  const today = new Date().toISOString().split('T')[0]; // YYYY-MM-DD для input[type=date]
  document.getElementById('fDate').value = today;
  document.getElementById('fQty').value  = '';
  document.getElementById('fPrice').value = '';

  // Подсказка для количества
  document.getElementById('qtyHint').textContent =
    type === 'stock'
      ? 'Только целое число (например: 10)'
      : 'Можно дробное (например: 0.5)';

  document.getElementById('addForm').style.display = 'block';
  document.getElementById('addForm').scrollIntoView({ behavior: 'smooth' });
}

async function submitAsset() {
  const errEl = document.getElementById('formError');
  errEl.style.display = 'none';

  const type  = document.getElementById('selType').value;
  const code  = document.getElementById('selCode').value;
  const name  = document.getElementById('selName').value;
  const qty   = document.getElementById('fQty').value;
  const price = document.getElementById('fPrice').value;
  const date  = document.getElementById('fDate').value; // YYYY-MM-DD

  // Локальная валидация
  if (!qty || !price || !date) {
    return showError(errEl, 'Заполните все поля');
  }
  const qtyN   = parseFloat(qty);
  const priceN = parseFloat(price);
  if (isNaN(qtyN) || qtyN <= 0) {
    return showError(errEl, 'Количество должно быть положительным числом');
  }
  if (type === 'stock' && !Number.isInteger(qtyN)) {
    return showError(errEl, 'Количество акций должно быть целым числом');
  }
  if (isNaN(priceN) || priceN <= 0) {
    return showError(errEl, 'Цена должна быть положительным числом');
  }

  // Конвертируем дату из YYYY-MM-DD в ДД.ММ.ГГГГ для хранения
  const [y, m, d2] = date.split('-');
  const dateFormatted = `${d2}.${m}.${y}`;

  const body = { type, code, name, quantity: qtyN, purchase_price: priceN, purchase_date: dateFormatted };
  const r    = await fetch('/api/assets', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const res = await r.json();

  if (!res.success) {
    return showError(errEl, res.error || 'Ошибка сервера');
  }

  closeModal();
  loadAll();
}

function showError(el, msg) {
  el.textContent = msg;
  el.style.display = 'block';
}

// ═══ Настройки ═══════════════════════════════════════════════
function toggleSettings() {
  document.getElementById('settingsPanel').classList.toggle('open');
}

function setCurrency(cur) {
  currency = cur;
  localStorage.setItem('sc_currency', cur);
  syncCurButtons();
  loadAll();
}

function syncCurButtons() {
  document.querySelectorAll('.cur-btn').forEach(b => {
    b.classList.toggle('active', b.dataset.cur === currency);
  });
}

function toggleTheme() {
  const isDark = document.documentElement.classList.toggle('dark');
  const btn = document.getElementById('themeToggle');
  btn.classList.toggle('on', isDark);
  btn.setAttribute('aria-checked', isDark);
  localStorage.setItem('sc_theme', isDark ? 'dark' : 'light');
}

function applyTheme(dark) {
  document.documentElement.classList.toggle('dark', dark);
  const btn = document.getElementById('themeToggle');
  if (btn) {
    btn.classList.toggle('on', dark);
    btn.setAttribute('aria-checked', dark);
  }
}

// ═══ Форматирование ═══════════════════════════════════════════
function fmt(n) {
  return n.toLocaleString('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}
