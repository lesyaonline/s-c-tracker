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

  // Ограничение максимальной даты покупки — сегодня
  const dateInput = document.getElementById('fDate');
  if (dateInput) {
    dateInput.max = new Date().toISOString().split('T')[0];
    dateInput.value = new Date().toISOString().split('T')[0];
  }

  loadAll();
  setInterval(loadAll, 60_000);

  document.getElementById('modal').addEventListener('click', e => {
    if (e.target.id === 'modal') closeModal();
  });
  document.getElementById('deleteModal').addEventListener('click', e => {
    if (e.target.id === 'deleteModal') closeDeleteModal();
  });
  document.addEventListener('click', e => {
    const wrap = document.querySelector('.settings-wrap');
    if (wrap && !wrap.contains(e.target)) {
      document.getElementById('settingsPanel').classList.remove('open');
    }
  });
});

// ═══ Загрузка всего ═══════════════════════════════════════════
async function loadAll() {
  showChartLoading();

  // Один запрос вместо двух — виджет вычисляется из тех же данных что и таблица
  const [assetsData, ratesData] = await Promise.all([
    fetch(`/api/assets?currency=${currency}`).then(r => r.json()),
    fetch('/api/rates').then(r => r.json()),
  ]);

  // Статистика виджета = сумма прибылей/убытков каждого актива
  const stats = computeStats(assetsData);
  renderStats(stats, ratesData);
  renderAssets(assetsData);

  await loadChart();
}

// ═══ Статистика из данных активов (единый источник правды) ════
function computeStats(assets) {
  const sym = assets[0]?.currency_symbol || '$';
  let invest = 0, current = 0;
  for (const a of assets) {
    invest  += a.invest_value;   // сумма покупок
    current += a.current_value;  // текущая стоимость
  }
  const profit = current - invest;
  const pct    = invest > 0 ? (profit / invest * 100) : 0;
  return { total_investment: invest, total_current: current,
           total_profit: profit, profit_percent: pct, currency_symbol: sym };
}

// ═══ Рендер виджета баланса ════════════════════════════════════
function renderStats(s, rates) {
  const sym  = s.currency_symbol;
  const sign = v => v >= 0 ? '+' : '';

  document.getElementById('bwAmount').textContent   = sym + fmtShort(s.total_current);
  document.getElementById('bwInvested').textContent = sym + fmtShort(s.total_investment);

  const profitEl = document.getElementById('bwProfit');
  profitEl.textContent = sign(s.total_profit) + sym + fmtShort(Math.abs(s.total_profit));
  profitEl.style.color = s.total_profit >= 0 ? '#86efac' : '#fca5a5';

  const pctEl = document.getElementById('bwPct');
  pctEl.textContent = sign(s.profit_percent) + s.profit_percent.toFixed(2) + '%';
  pctEl.style.color = s.profit_percent >= 0 ? '#86efac' : '#fca5a5';

  if (rates) {
    document.getElementById('rateUsd').textContent = `USD/RUB: ${rates.usd_rub.toFixed(2)}`;
    document.getElementById('rateCny').textContent = `CNY/RUB: ${rates.cny_rub.toFixed(2)}`;
  }
}

async function loadStats() {
  const [assetsData, ratesData] = await Promise.all([
    fetch(`/api/assets?currency=${currency}`).then(r => r.json()),
    fetch('/api/rates').then(r => r.json()),
  ]);
  renderStats(computeStats(assetsData), ratesData);
}

// ═══ Таблица активов (сгруппированные строки) ═════════════════
function renderAssets(assets) {
  // Собираем HTML в строки — DOM трогаем один раз, без промежуточного сброса
  let stockHtml = '';
  let cryptoHtml = '';
  let hasStocks = false, hasCrypto = false;

  assets.forEach(a => {
    const sym  = a.currency_symbol;
    const cls  = a.profit >= 0 ? 'pos' : 'neg';
    const sign = a.profit >= 0 ? '+' : '';

    const badge = a.type === 'stock'
      ? '<span class="badge badge-s">Акция</span>'
      : '<span class="badge badge-c">Крипта</span>';

    // Количество: акции — целые, крипта — до 6 знаков
    const qtyFmt = a.type === 'stock'
      ? parseInt(a.quantity)
      : a.quantity.toLocaleString('ru-RU', { maximumFractionDigits: 6 });

    // Кнопка удаляет всю группу через ids
    const idsJson  = JSON.stringify(a.ids).replace(/"/g, '&quot;');
    const safeName = a.name.replace(/'/g, "\\'");

    const row = `
      <tr>
        <td>
          <div class="a-name">${a.name}${badge}</div>
          <div class="a-sub">${a.code}</div>
        </td>
        <td>${qtyFmt}</td>
        <td>${sym}${fmt(a.avg_buy_price)}</td>
        <td>${sym}${fmt(a.current_price)}</td>
        <td>${sym}${fmt(a.invest_value)}</td>
        <td>${sym}${fmt(a.current_value)}</td>
        <td class="${cls}">${sign}${sym}${fmt(Math.abs(a.profit))}<br>
          <span style="font-size:11px;opacity:.8">${sign}${a.profit_percent.toFixed(2)}%</span>
        </td>
        <td>
          <button class="btn-del"
            onclick="openDeleteModal(${idsJson}, '${safeName}', ${a.quantity}, '${a.type}')">
            Удалить
          </button>
        </td>
      </tr>`;

    if (a.type === 'stock') { stockHtml += row; hasStocks = true; }
    else                    { cryptoHtml += row; hasCrypto = true; }
  });

  // Единственное обращение к DOM — старые значения видны вплоть до этого момента
  document.getElementById('stocksBody').innerHTML =
    hasStocks ? stockHtml : '<tr class="empty-row"><td colspan="8">Акций пока нет</td></tr>';
  document.getElementById('cryptoBody').innerHTML =
    hasCrypto ? cryptoHtml : '<tr class="empty-row"><td colspan="8">Криптовалют пока нет</td></tr>';
}

async function loadAssets() {
  const assets = await fetch(`/api/assets?currency=${currency}`).then(r => r.json());
  renderAssets(assets);
}

// ═══ Оверлей загрузки графика ══════════════════════════════════
function showChartLoading() {
  const el = document.getElementById('chartOverlay');
  if (el) el.classList.remove('hidden');
}
function hideChartLoading() {
  const el = document.getElementById('chartOverlay');
  if (el) el.classList.add('hidden');
}

// ═══ График ═══════════════════════════════════════════════════
async function loadChart() {
  const r = await fetch(`/api/portfolio/chart?days=${chartDays}&currency=${currency}`);
  const d = await r.json();

  const ctx = document.getElementById('portfolioChart').getContext('2d');
  if (portfolio) portfolio.destroy();

  const isUp      = d.data.length > 1 && d.data[d.data.length - 1] >= d.data[0];
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

  // График построен — убираем оверлей загрузки
  hideChartLoading();
}

// ═══ Период графика ═══════════════════════════════════════════
function setPeriod(days, btn) {
  chartDays = days;
  document.querySelectorAll('.p-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  showChartLoading();
  loadChart();
}

// ═══ Удаление группы активов ══════════════════════════════════
// ═══ Модал удаления с выбором количества ══════════════════════
let _delTarget = null;

function openDeleteModal(ids, name, totalQty, type) {
  _delTarget = { ids, name, totalQty, type };

  document.getElementById('deleteInfo').innerHTML =
    `<strong>${name}</strong><br>
     <span style="opacity:.75">В портфеле: <strong>${
       type === 'stock'
         ? parseInt(totalQty)
         : totalQty.toLocaleString('ru-RU', { maximumFractionDigits: 6 })
     }</strong> ед.</span>`;

  const inp = document.getElementById('deleteQtyInput');
  inp.step  = type === 'stock' ? '1' : 'any';
  inp.max   = totalQty;
  inp.value = type === 'stock' ? parseInt(totalQty) : totalQty;

  document.getElementById('deleteQtyHint').textContent =
    type === 'stock'
      ? `Целое число от 1 до ${parseInt(totalQty)}`
      : `Число от 0.000001 до ${totalQty}`;

  document.getElementById('deleteError').style.display = 'none';
  document.getElementById('deleteModal').classList.add('active');
}

function closeDeleteModal() {
  document.getElementById('deleteModal').classList.remove('active');
  _delTarget = null;
}

async function confirmDelete() {
  if (!_delTarget) return;
  const errEl = document.getElementById('deleteError');
  const qty   = parseFloat(document.getElementById('deleteQtyInput').value);

  if (isNaN(qty) || qty <= 0) {
    errEl.textContent = 'Укажите корректное количество';
    errEl.style.display = 'block'; return;
  }
  if (qty > _delTarget.totalQty + 1e-9) {
    errEl.textContent = `Нельзя удалить больше ${_delTarget.totalQty}`;
    errEl.style.display = 'block'; return;
  }
  if (_delTarget.type === 'stock' && !Number.isInteger(qty)) {
    errEl.textContent = 'Количество акций должно быть целым числом';
    errEl.style.display = 'block'; return;
  }

  const isAll = Math.abs(qty - _delTarget.totalQty) < 1e-9;

  if (isAll) {
    await fetch('/api/assets/group', {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ids: _delTarget.ids }),
    });
  } else {
    await fetch('/api/assets/group/partial', {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ids: _delTarget.ids, quantity: qty }),
    });
  }

  closeDeleteModal();
  loadAll();
}

// Оставляем deleteGroup как алиас для совместимости
async function deleteGroup(ids) {
  if (!confirm('Удалить этот актив (все записи) из портфеля?')) return;
  await fetch('/api/assets/group', {
    method: 'DELETE',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ids }),
  });
  loadAll();
}

// ═══ Модальное окно ═══════════════════════════════════════════
function openModal() {
  selected = null;
  document.querySelectorAll('.asset-card').forEach(c => c.classList.remove('selected'));
  document.getElementById('addForm').style.display  = 'none';
  document.getElementById('formError').style.display = 'none';
  document.getElementById('assetSearch').value       = '';
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
  document.querySelectorAll('.asset-card').forEach(c => c.classList.remove('selected'));
  event.currentTarget.classList.add('selected');

  selected = { type, code, name };
  document.getElementById('selectedBanner').textContent = `Выбрано: ${name} (${code})`;
  document.getElementById('selType').value = type;
  document.getElementById('selCode').value = code;
  document.getElementById('selName').value = name;

  // Сброс и установка ограничения даты
  const today = new Date().toISOString().split('T')[0];
  const dateEl = document.getElementById('fDate');
  dateEl.max   = today;
  dateEl.value = today;

  document.getElementById('fQty').value   = '';
  document.getElementById('fPrice').value = '';
  document.getElementById('fCurrency').value = 'usd';

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

  const type     = document.getElementById('selType').value;
  const code     = document.getElementById('selCode').value;
  const name     = document.getElementById('selName').value;
  const qty      = document.getElementById('fQty').value;
  const price    = document.getElementById('fPrice').value;
  const date     = document.getElementById('fDate').value;     // YYYY-MM-DD
  const priceCur = document.getElementById('fCurrency').value; // usd|rub|cny

  if (!qty || !price || !date) return showError(errEl, 'Заполните все поля');

  const qtyN   = parseFloat(qty);
  const priceN = parseFloat(price);

  if (isNaN(qtyN) || qtyN <= 0)
    return showError(errEl, 'Количество должно быть положительным числом');
  if (type === 'stock' && !Number.isInteger(qtyN))
    return showError(errEl, 'Количество акций должно быть целым числом');
  if (isNaN(priceN) || priceN <= 0)
    return showError(errEl, 'Цена должна быть положительным числом');

  // Проверка даты на клиенте — не из будущего
  const selectedDate = new Date(date);
  const today        = new Date();
  today.setHours(23, 59, 59, 999);
  if (selectedDate > today) return showError(errEl, 'Дата покупки не может быть в будущем');

  // Конвертируем дату YYYY-MM-DD → ДД.ММ.ГГГГ
  const [y, m, d2] = date.split('-');
  const dateFormatted = `${d2}.${m}.${y}`;

  const body = {
    type, code, name,
    quantity:          qtyN,
    purchase_price:    priceN,
    purchase_currency: priceCur,
    purchase_date:     dateFormatted,
  };

  const r   = await fetch('/api/assets', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const res = await r.json();
  if (!res.success) return showError(errEl, res.error || 'Ошибка сервера');

  closeModal();
  loadAll();
}

function showError(el, msg) {
  el.textContent    = msg;
  el.style.display  = 'block';
}

// ═══ Настройки ════════════════════════════════════════════════
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
  const btn    = document.getElementById('themeToggle');
  btn.classList.toggle('on', isDark);
  btn.setAttribute('aria-checked', isDark);
  localStorage.setItem('sc_theme', isDark ? 'dark' : 'light');
}

function applyTheme(dark) {
  document.documentElement.classList.toggle('dark', dark);
  const btn = document.getElementById('themeToggle');
  if (btn) { btn.classList.toggle('on', dark); btn.setAttribute('aria-checked', dark); }
}

// ═══ Форматирование ═══════════════════════════════════════════
function fmt(n) {
  if (n === undefined || n === null || isNaN(n)) return '0.00';
  return n.toLocaleString('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

// Компактный формат для виджета: 1 234 567 → 1.2M, 85 000 → 85K
function fmtShort(n) {
  if (n === undefined || n === null || isNaN(n)) return '0';
  const abs  = Math.abs(n);
  const sign = n < 0 ? '−' : '';
  if (abs >= 1_000_000_000) return sign + (abs / 1_000_000_000).toFixed(1).replace(/\.0$/, '') + 'B';
  if (abs >= 1_000_000)     return sign + (abs / 1_000_000).toFixed(1).replace(/\.0$/, '')     + 'M';
  if (abs >= 100_000)       return sign + (abs / 1_000).toFixed(0)                              + 'K';
  if (abs >= 10_000)        return sign + (abs / 1_000).toFixed(1).replace(/\.0$/, '')          + 'K';
  return sign + abs.toLocaleString('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}
