/* GTA6 PS5 AI — first-run setup wizard. Talks to setup_api.py + server.py on 127.0.0.1. */
(() => {
'use strict';

// ------------------------------------------------------------------ i18n
const T = {
  en: {
    setup: 'Setup', openRemote: 'Open remote', stepOf: 'Step {n} of {total}',
    back: 'Back', next: 'Continue', skip: 'Skip for now', finish: 'Finish setup', finishGo: 'Finish & open remote',
    s_find: 'Find PS5', s_find_d: 'Network & console', s_permissions: 'Console permissions', s_permissions_d: 'Required settings',
    s_psn: 'PlayStation account', s_psn_d: 'Sign in with NPSSO', s_link: 'Link console', s_link_d: '8-digit code',
    s_brain: 'AI brain', s_brain_d: 'Claude Code CLI', s_test: 'Test drive', s_test_d: 'Live picture & buttons',
    s_play: 'Play', s_play_d: 'Start the bot',
    p_on: 'PS5 on', p_rest: 'PS5 in rest mode', p_off: 'PS5 not found', p_psn: 'PSN: {u}', p_nopsn: 'PSN not signed in',
    p_linked: 'Linked', p_nolink: 'Not linked', p_brain: 'Brain ready', p_brain_login: 'Brain: sign in needed',
    p_brain_missing: 'Brain not installed', p_brain_chk: 'Checking brain…', p_bot: 'Bot running', p_conn: 'Streaming',
    // step 1
    find_t: 'Find your PS5', find_l: 'Turn the console on and keep it on the same network as this computer. We look for it automatically.',
    scanning: 'Looking for PlayStation 5 on your network…', rescan: 'Scan again', none: 'No PS5 answered. Make sure it is on (or in rest mode with network standby) and on the same network. Or enter its IP below.',
    manual: 'Enter IP address manually', use: 'Use this IP', fw: 'Firmware', saved: 'Saved. The app will use {h}.', selected: 'Selected',
    pw_on: 'On', pw_standby: 'Rest mode', pw_unknown: 'Unknown', ip_hint: 'Find it on PS5: Settings → Network → Connection Status → View Connection Status.',
    net_t: 'Network check', net_run: 'Check network', net_rerun: 'Check again', net_conn: 'This computer', net_ping: 'Ping to PS5',
    net_jitter: 'Jitter', net_loss: 'Packet loss', wifi: 'Wi-Fi', ethernet: 'Ethernet', vpn: 'VPN', other: 'Other', unknown: 'Unknown',
    net_wifi_t: 'This computer is on Wi-Fi', net_wifi: 'Remote Play over Wi-Fi drops frames and adds 20–80 ms of lag in bursts, so the bot sees late pictures and steers wrong. Connect BOTH the PS5 and this computer to the router with Ethernet cables for reliable play.',
    net_bad_t: 'The connection to PS5 is unstable', net_bad: 'High latency, jitter or packet loss. Use cables, move closer to the router or close heavy downloads.',
    net_good_t: 'Network looks great', net_good: 'Wired and fast — ideal for Remote Play.',
    net_nohost: 'Choose a PS5 first, then we measure the link to it.', net_noreply: 'The PS5 did not answer pings. It may be off — turn it on and press “Check again”.',
    // step 2
    perm_t: 'Allow Remote Play on the console', perm_l: 'These settings live on the PS5 itself. Go through each one with the controller and tick it off — the bot cannot work without them.',
    perm_hint: 'Tick all four to continue', settings: 'Settings', system: 'System',
    rp_t: 'Enable Remote Play', rp_p: ['Settings', 'System', 'Remote Play', 'Enable Remote Play'], rp_d: 'Turn the switch on.',
    rest_t: 'Keep the PS5 reachable in rest mode', rest_p: ['Settings', 'System', 'Power Saving', 'Features Available in Rest Mode'],
    rest_d: 'Turn on both: “Stay Connected to the Internet” and “Enable Turning On PS5 from Network”. Then the bot can wake the console.',
    user_t: 'The same PSN account on PS5', user_p: ['Settings', 'Users and Accounts', 'Other', 'Console Sharing and Offline Play', 'Enable'],
    user_d: 'Sign in on the PS5 with the account you will use in step 3, and allow Remote Play for that user (child accounts need it allowed in Family Management).',
    user_err_t: 'Why: error 0x80108b12', user_err: 'The PS5 rejects a Remote Play session with 0x80108b12 when the PSN account of this computer is not signed in on the console, is not its primary account, or Remote Play is blocked for it by parental controls. Signing in that same user on the PS5 and enabling Console Sharing fixes it.',
    link_t: 'Open “Link Device”', link_p: ['Settings', 'System', 'Remote Play', 'Link Device'], link_d: 'The PS5 shows an 8-digit code valid for about 5 minutes. Keep it on screen for step 4.',
    v_reach: 'PS5 answers on the network', v_reach_no: 'Can’t verify while PS5 is offline', v_rest: 'Answers in rest mode — network standby works',
    v_rest_on: 'Verified next time the PS5 rests', v_user: 'This computer: {u}', v_user_no: 'Verified after step 3', v_linked: 'Already linked', v_link_no: 'Verified after step 4',
    // step 3
    psn_t: 'Sign in to PlayStation Network', psn_l: 'We never ask for your password. You copy a sign-in token (NPSSO) from Sony’s own site in your browser.',
    psn_1: 'Open {a} in your browser and sign in with the <b>same account</b> as on the PS5.',
    psn_2: 'Then open {a}. You will see text like <code>{"npsso":"…"}</code>.',
    psn_3: 'Copy the whole text (or just the 64-character value) and paste it here.',
    psn_ph: 'Paste NPSSO or {"npsso":"…"}', psn_btn: 'Sign in', psn_ok: 'Signed in as {u}', psn_change: 'Use another account',
    psn_len: '{n}/64 characters', psn_safe: 'The token stays on this computer in .env.local. Treat it like a password: never share it or screenshots of it.',
    psn_bad: 'NPSSO is 64 characters. Copy it again.',
    // step 4
    lnk_t: 'Link this computer to the PS5', lnk_l: 'On the PS5 open Settings → System → Remote Play → Link Device and type the 8 digits you see.',
    lnk_btn: 'Link', lnk_ok: 'Linked to {n}', lnk_need_psn: 'Sign in to PSN first (step 3).', lnk_need_on: 'The PS5 must be turned on (not in rest mode) to link.',
    lnk_again: 'Link again',
    // step 5
    br_t: 'Connect the AI brain', br_l: 'The bot thinks with Claude Code — the official Claude CLI, running on your own Claude subscription.',
    br_status: 'Status', br_path: 'Location', br_version: 'Version', br_account: 'Account', br_ready: 'Installed and signed in',
    br_login: 'Installed, sign-in needed', br_missing: 'Not installed', br_unknown: 'Installed — sign-in unknown',
    br_install_t: 'Install Claude Code', br_install_l: 'Run one of these in {s}, or let us run it for you.',
    br_native: 'Official installer', br_npm: 'npm (needs Node.js 18+)', br_do_native: 'Install for me', br_do_npm: 'Install via npm',
    br_installing: 'Installing…', br_inst_ok: 'Installed. Checking…', br_inst_fail: 'Install failed (exit {c}). See the log.',
    br_signin: 'Sign in', br_signin_h: 'A terminal opens with <code>claude</code>. Type <code>/login</code>, finish in the browser, then press Recheck.',
    br_recheck: 'Recheck', br_test: 'Send a test prompt', br_test_ok: 'Brain replied in {ms} ms', br_test_fail: 'Test failed: {e}',
    br_path_warn: 'Claude is installed but not on PATH. The bot calls <code>claude</code> by name — add {d} to PATH or restart the app.',
    copy: 'Copy', copied: 'Copied',
    // step 6
    t_t: 'Test drive', t_l: 'See the live PS5 picture and press a button. If you see the screen move, everything works.',
    t_connect: 'Connect', t_disconnect: 'Disconnect', t_wake: 'Wake PS5', t_wait: 'Waiting for picture…',
    t_frame: 'Frame fetch', t_press: 'Button round-trip', t_age: 'Frame age', t_rate: 'Preview rate',
    t_ok: 'Picture received — Remote Play works.',
    // step 7
    pl_t: 'Let the AI play', pl_l: 'Choose what the bot should do, then start. Open GTA 6 and stand in the world before starting.',
    m_car: 'Steal a car', m_car_d: 'Find, steal and drive to the waypoint', m_drive: 'Free drive', m_drive_d: 'Drive to the map marker',
    m_goto: 'Walk to waypoint', m_goto_d: 'On foot, avoiding obstacles', m_mission: 'Mission / fight', m_mission_d: 'Survive firefights',
    pl_dur: 'Duration', pl_min: 'min', pl_start: 'Start bot', pl_stop: 'Stop bot', pl_running: 'Running · {m} · {t}',
    pl_idle: 'Not running', pl_exit: 'Finished (exit {c})', pl_log: 'Bot log',
    ov_t: 'Stream overlay for OBS', ov_l: 'Add a Browser Source with this URL, 1920×1080, transparent background. It shows what the AI thinks.',
    open: 'Open', done_t: 'Setup complete', done_l: 'You can always come back to /setup.',
    err: 'Something went wrong', offline: 'Server not reachable. Is the app running?',
  },
  ru: {
    setup: 'Настройка', openRemote: 'Открыть пульт', stepOf: 'Шаг {n} из {total}',
    back: 'Назад', next: 'Продолжить', skip: 'Пропустить пока', finish: 'Завершить настройку', finishGo: 'Готово — к пульту',
    s_find: 'Найти PS5', s_find_d: 'Сеть и консоль', s_permissions: 'Разрешения консоли', s_permissions_d: 'Обязательные настройки',
    s_psn: 'Аккаунт PlayStation', s_psn_d: 'Вход по NPSSO', s_link: 'Привязка консоли', s_link_d: 'Код из 8 цифр',
    s_brain: 'ИИ-мозг', s_brain_d: 'Claude Code CLI', s_test: 'Проверка', s_test_d: 'Картинка и кнопки',
    s_play: 'Играть', s_play_d: 'Запуск бота',
    p_on: 'PS5 включена', p_rest: 'PS5 в режиме покоя', p_off: 'PS5 не найдена', p_psn: 'PSN: {u}', p_nopsn: 'PSN: вход не выполнен',
    p_linked: 'Привязана', p_nolink: 'Не привязана', p_brain: 'Мозг готов', p_brain_login: 'Мозг: нужен вход',
    p_brain_missing: 'Мозг не установлен', p_brain_chk: 'Проверяем мозг…', p_bot: 'Бот играет', p_conn: 'Трансляция',
    find_t: 'Найдите свою PS5', find_l: 'Включите консоль — она должна быть в той же сети, что и этот компьютер. Мы ищем её автоматически.',
    scanning: 'Ищем PlayStation 5 в вашей сети…', rescan: 'Искать снова', none: 'PS5 не ответила. Проверьте, что она включена (или в режиме покоя с сетью) и в той же сети. Или введите её IP ниже.',
    manual: 'Ввести IP-адрес вручную', use: 'Использовать', fw: 'Прошивка', saved: 'Сохранено. Используем {h}.', selected: 'Выбрана',
    pw_on: 'Включена', pw_standby: 'Режим покоя', pw_unknown: 'Неизвестно', ip_hint: 'Где посмотреть на PS5: Настройки → Сеть → Состояние подключения → Посмотреть состояние подключения.',
    net_t: 'Проверка сети', net_run: 'Проверить сеть', net_rerun: 'Проверить снова', net_conn: 'Этот компьютер', net_ping: 'Пинг до PS5',
    net_jitter: 'Джиттер', net_loss: 'Потери', wifi: 'Wi-Fi', ethernet: 'Кабель', vpn: 'VPN', other: 'Другое', unknown: 'Неизвестно',
    net_wifi_t: 'Компьютер подключён по Wi-Fi', net_wifi: 'По Wi-Fi Remote Play теряет кадры и рывками добавляет 20–80 мс задержки — бот видит картинку с опозданием и рулит мимо. Подключите И PS5, И этот компьютер к роутеру кабелем Ethernet.',
    net_bad_t: 'Связь с PS5 нестабильна', net_bad: 'Высокая задержка, джиттер или потери пакетов. Используйте кабель, подвиньтесь к роутеру или остановите тяжёлые загрузки.',
    net_good_t: 'Сеть отличная', net_good: 'Кабель и низкая задержка — идеально для Remote Play.',
    net_nohost: 'Сначала выберите PS5 — потом измерим связь с ней.', net_noreply: 'PS5 не отвечает на пинг. Возможно, она выключена — включите и нажмите «Проверить снова».',
    perm_t: 'Разрешите дистанционную игру на консоли', perm_l: 'Эти настройки — на самой PS5. Пройдите каждую геймпадом и отметьте галочкой — без них бот работать не сможет.',
    perm_hint: 'Отметьте все четыре пункта', settings: 'Настройки', system: 'Система',
    rp_t: 'Включите дистанционную игру', rp_p: ['Настройки', 'Система', 'Дистанционная игра', 'Включить дистанционную игру'], rp_d: 'Переведите переключатель во «вкл».',
    rest_t: 'Оставьте PS5 доступной в режиме покоя', rest_p: ['Настройки', 'Система', 'Энергосбережение', 'Функции, доступные в режиме покоя'],
    rest_d: 'Включите оба пункта: «Сохранять подключение к интернету» и «Разрешить включение PS5 через сеть». Тогда бот сможет будить консоль.',
    user_t: 'Тот же аккаунт PSN на PS5', user_p: ['Настройки', 'Пользователи и учётные записи', 'Другое', 'Общий доступ к консоли и игра в автономном режиме', 'Включить'],
    user_d: 'Войдите на PS5 под тем же аккаунтом, что будет на шаге 3, и разрешите ему дистанционную игру (детским аккаунтам — в «Управлении семьёй»).',
    user_err_t: 'Зачем: ошибка 0x80108b12', user_err: 'PS5 отклоняет сеанс Remote Play с ошибкой 0x80108b12, если аккаунт PSN этого компьютера не вошёл на консоли, не является на ней основным или Remote Play для него запрещён родительским контролем. Решение — войти этим же пользователем на PS5 и включить «Общий доступ к консоли».',
    link_t: 'Откройте «Связать устройство»', link_p: ['Настройки', 'Система', 'Дистанционная игра', 'Связать устройство'], link_d: 'PS5 покажет код из 8 цифр — он действует около 5 минут. Оставьте его на экране для шага 4.',
    v_reach: 'PS5 отвечает в сети', v_reach_no: 'Проверим, когда PS5 будет в сети', v_rest: 'Отвечает в режиме покоя — сеть в покое работает',
    v_rest_on: 'Проверим, когда PS5 уйдёт в покой', v_user: 'На компьютере: {u}', v_user_no: 'Проверим после шага 3', v_linked: 'Уже привязана', v_link_no: 'Проверим после шага 4',
    psn_t: 'Вход в PlayStation Network', psn_l: 'Пароль мы никогда не спрашиваем. Вы сами копируете токен входа (NPSSO) с сайта Sony в своём браузере.',
    psn_1: 'Откройте {a} в браузере и войдите под <b>тем же аккаунтом</b>, что на PS5.',
    psn_2: 'Затем откройте {a}. Появится текст вида <code>{"npsso":"…"}</code>.',
    psn_3: 'Скопируйте весь текст (или только значение из 64 символов) и вставьте сюда.',
    psn_ph: 'Вставьте NPSSO или {"npsso":"…"}', psn_btn: 'Войти', psn_ok: 'Вход выполнен: {u}', psn_change: 'Другой аккаунт',
    psn_len: '{n}/64 символов', psn_safe: 'Токен остаётся на этом компьютере в .env.local. Это как пароль: никому не передавайте и не скриньте.',
    psn_bad: 'В NPSSO ровно 64 символа. Скопируйте заново.',
    lnk_t: 'Привяжите компьютер к PS5', lnk_l: 'На PS5 откройте Настройки → Система → Дистанционная игра → Связать устройство и введите 8 цифр с экрана.',
    lnk_btn: 'Привязать', lnk_ok: 'Привязано к {n}', lnk_need_psn: 'Сначала войдите в PSN (шаг 3).', lnk_need_on: 'Для привязки PS5 должна быть включена (не в режиме покоя).',
    lnk_again: 'Привязать заново',
    br_t: 'Подключите ИИ-мозг', br_l: 'Бот думает через Claude Code — официальный CLI Claude на вашей собственной подписке.',
    br_status: 'Статус', br_path: 'Где', br_version: 'Версия', br_account: 'Аккаунт', br_ready: 'Установлен, вход выполнен',
    br_login: 'Установлен, нужен вход', br_missing: 'Не установлен', br_unknown: 'Установлен — вход не проверен',
    br_install_t: 'Установите Claude Code', br_install_l: 'Выполните одну из команд в {s} — или нажмите, и мы установим сами.',
    br_native: 'Официальный установщик', br_npm: 'npm (нужен Node.js 18+)', br_do_native: 'Установить', br_do_npm: 'Установить через npm',
    br_installing: 'Устанавливаем…', br_inst_ok: 'Установлено. Проверяем…', br_inst_fail: 'Установка не удалась (код {c}). Смотрите лог.',
    br_signin: 'Войти', br_signin_h: 'Откроется терминал с <code>claude</code>. Введите <code>/login</code>, завершите вход в браузере и нажмите «Проверить снова».',
    br_recheck: 'Проверить снова', br_test: 'Тестовый запрос', br_test_ok: 'Мозг ответил за {ms} мс', br_test_fail: 'Тест не прошёл: {e}',
    br_path_warn: 'Claude установлен, но его нет в PATH. Бот вызывает <code>claude</code> по имени — добавьте {d} в PATH или перезапустите приложение.',
    copy: 'Копировать', copied: 'Скопировано',
    t_t: 'Проверка', t_l: 'Живая картинка с PS5 и кнопки. Если экран реагирует — всё работает.',
    t_connect: 'Подключить', t_disconnect: 'Отключить', t_wake: 'Разбудить PS5', t_wait: 'Ждём картинку…',
    t_frame: 'Загрузка кадра', t_press: 'Отклик кнопки', t_age: 'Возраст кадра', t_rate: 'Частота превью',
    t_ok: 'Картинка есть — Remote Play работает.',
    pl_t: 'Пусть ИИ играет', pl_l: 'Выберите задачу и запустите. Перед стартом откройте GTA 6 и встаньте в игровом мире.',
    m_car: 'Угнать машину', m_car_d: 'Найти, угнать и доехать до метки', m_drive: 'Свободная езда', m_drive_d: 'Ехать к метке на карте',
    m_goto: 'Дойти до метки', m_goto_d: 'Пешком, обходя препятствия', m_mission: 'Миссия / бой', m_mission_d: 'Выжить в перестрелке',
    pl_dur: 'Длительность', pl_min: 'мин', pl_start: 'Запустить бота', pl_stop: 'Остановить', pl_running: 'Играет · {m} · {t}',
    pl_idle: 'Не запущен', pl_exit: 'Завершён (код {c})', pl_log: 'Лог бота',
    ov_t: 'Оверлей для OBS', ov_l: 'Добавьте «Браузер» с этим адресом, 1920×1080, прозрачный фон. Он показывает, о чём думает ИИ.',
    open: 'Открыть', done_t: 'Настройка завершена', done_l: 'Вернуться сюда можно в любой момент: /setup.',
    err: 'Что-то пошло не так', offline: 'Сервер недоступен. Приложение запущено?',
  },
};
let lang = 'en';
try { lang = localStorage.getItem('ps5setup.lang') || ''; } catch (e) { lang = ''; }
if (!T[lang]) lang = (navigator.language || 'en').toLowerCase().startsWith('ru') ? 'ru' : 'en';
const t = (k, v) => { let s = T[lang][k] ?? T.en[k] ?? k; if (v && typeof s === 'string') for (const [a, b] of Object.entries(v)) s = s.split('{' + a + '}').join(b); return s; };

// ------------------------------------------------------------------ utils
const $ = (s, r = document) => r.querySelector(s);
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const CHECK = '<svg class="check" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M4.5 12.5l5 5 10-11"/></svg>';
const ICON = {
  warn: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3l9.5 17h-19z"/><path d="M12 10v4M12 17.5v.01"/></svg>',
  ok: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9.5"/><path d="M7.5 12.5l3 3 6-6.5"/></svg>',
  info: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="9.5"/><path d="M12 11v6M12 7.5v.01"/></svg>',
  ps5: '<svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"><path d="M7 3c-1.5 2-2 6-2 9s.5 7 2 9h2c-.8-2-1-5-1-9s.2-7 1-9z"/><path d="M17 3c1.5 2 2 6 2 9s-.5 7-2 9h-2c.8-2 1-5 1-9s-.2-7-1-9z"/><path d="M10 6h4v12h-4z"/></svg>',
  copy: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="8" y="8" width="12" height="12" rx="2.5"/><path d="M16 8V6a2 2 0 00-2-2H6a2 2 0 00-2 2v8a2 2 0 002 2h2"/></svg>',
  ext: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 01-1 1H5a1 1 0 01-1-1V7a1 1 0 011-1h5"/></svg>',
  car: '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"><path d="M4 16v-4l2-5h12l2 5v4z"/><circle cx="7.5" cy="16.5" r="1.8"/><circle cx="16.5" cy="16.5" r="1.8"/><path d="M4 12h16"/></svg>',
  wheel: '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="8.5"/><circle cx="12" cy="12" r="2"/><path d="M3.5 12H10M14 12h6.5M12 14v6.5"/></svg>',
  pin: '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"><path d="M12 21s-6.5-6-6.5-11a6.5 6.5 0 0113 0c0 5-6.5 11-6.5 11z"/><circle cx="12" cy="10" r="2.3"/></svg>',
  target: '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="3"/><path d="M12 1.5V5M12 19v3.5M1.5 12H5M19 12h3.5"/></svg>',
};
const FACE = {
  CROSS: '<svg viewBox="0 0 24 24" fill="none" stroke="#5b8cff" stroke-width="2.6" stroke-linecap="round"><path d="M6 6l12 12M18 6L6 18"/></svg>',
  CIRCLE: '<svg viewBox="0 0 24 24" fill="none" stroke="#ff5a6a" stroke-width="2.6"><circle cx="12" cy="12" r="7"/></svg>',
  TRIANGLE: '<svg viewBox="0 0 24 24" fill="none" stroke="#1fbf98" stroke-width="2.4" stroke-linejoin="round"><path d="M12 5l7.5 13h-15z"/></svg>',
  SQUARE: '<svg viewBox="0 0 24 24" fill="none" stroke="#d872c8" stroke-width="2.4"><rect x="5.5" y="5.5" width="13" height="13" rx="1"/></svg>',
};

async function api(path, opts = {}) {
  const init = { method: opts.method || (opts.body ? 'POST' : 'GET'), headers: { 'X-Client': 'setup' } };
  if (opts.body !== undefined) { init.headers['Content-Type'] = 'application/json'; init.body = JSON.stringify(opts.body); }
  try {
    const r = await fetch(path, init);
    const j = await r.json().catch(() => ({}));
    if (!r.ok && j.ok === undefined) j.ok = false;
    return j;
  } catch (e) { return { ok: false, error: t('offline'), offline: true }; }
}
let toastTimer;
function toast(msg) { const el = $('#toast'); el.textContent = msg; el.classList.add('show'); clearTimeout(toastTimer); toastTimer = setTimeout(() => el.classList.remove('show'), 2200); }
async function copy(text) { try { await navigator.clipboard.writeText(text); toast(t('copied')); } catch (e) { toast(text); } }
const fmtFw = (v) => (v && /^\d{8}$/.test(v)) ? `${parseInt(v.slice(0, 2), 10)}.${v.slice(2, 4)}` : (v || '—');
const pwLabel = (p) => t(p === 'on' ? 'pw_on' : p === 'standby' ? 'pw_standby' : 'pw_unknown');
function busy(btn, on) { if (!btn) return; if (on) { btn.dataset.label = btn.innerHTML; btn.innerHTML = '<span class="spin"></span>' + btn.dataset.label; btn.disabled = true; } else { if (btn.dataset.label) btn.innerHTML = btn.dataset.label; btn.disabled = false; } }
function banner(kind, title, text) { return `<div class="banner ${kind}">${ICON[kind === 'bad' ? 'warn' : kind] || ICON.info}<div>${title ? `<b>${title}</b>` : ''}${text || ''}</div></div>`; }

// ------------------------------------------------------------------ PS5 screen mock (inline SVG, no Sony assets)
function psScreen({ crumb, side, sel = 0, rows = [], code }) {
  const W = 320, H = 180;
  let s = `<svg viewBox="0 0 ${W} ${H}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="${esc(crumb.join(' › '))}">
  <defs><linearGradient id="g${crumb.length}${rows.length}" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#0d1b3d"/><stop offset="1" stop-color="#03060f"/></linearGradient></defs>
  <rect width="${W}" height="${H}" fill="url(#g${crumb.length}${rows.length})"/>
  <text x="14" y="18" fill="#8ea2c8" font-size="7.5" font-family="-apple-system,Segoe UI,sans-serif">${esc(crumb.join('  ›  '))}</text>`;
  side.forEach((label, i) => {
    const y = 34 + i * 18;
    if (i === sel) s += `<rect x="10" y="${y - 11}" width="96" height="16" rx="4" fill="#ffffff" fill-opacity=".12"/>`;
    s += `<text x="16" y="${y}" fill="${i === sel ? '#fff' : '#7f8db0'}" font-size="8" font-weight="${i === sel ? 600 : 400}" font-family="-apple-system,Segoe UI,sans-serif">${esc(label.length > 20 ? label.slice(0, 19) + '…' : label)}</text>`;
  });
  s += `<line x1="114" y1="28" x2="114" y2="168" stroke="#ffffff" stroke-opacity=".08"/>`;
  if (code) {
    s += `<text x="216" y="70" fill="#9fb0d0" font-size="8" text-anchor="middle" font-family="-apple-system,Segoe UI,sans-serif">${esc(code.label)}</text>
    <rect x="140" y="80" width="152" height="38" rx="8" fill="#fff" fill-opacity=".07" stroke="#fff" stroke-opacity=".25"/>
    <text x="216" y="105" fill="#fff" font-size="20" font-weight="700" text-anchor="middle" letter-spacing="3" font-family="ui-monospace,Menlo,monospace">${esc(code.value)}</text>
    <text x="216" y="134" fill="#6f7fa3" font-size="7" text-anchor="middle" font-family="-apple-system,Segoe UI,sans-serif">5:00</text>`;
  }
  rows.forEach((r, i) => {
    const y = 34 + i * 26;
    s += `<rect x="122" y="${y - 12}" width="188" height="22" rx="5" fill="#fff" fill-opacity="${r.hl ? '.13' : '.04'}" ${r.hl ? 'stroke="#ffffff" stroke-opacity=".75" stroke-width="1"' : ''}/>`;
    const lbl = r.t.length > 34 ? r.t.slice(0, 33) + '…' : r.t;
    s += `<text x="130" y="${y + 2}" fill="${r.hl ? '#fff' : '#b4c0da'}" font-size="7.6" font-family="-apple-system,Segoe UI,sans-serif">${esc(lbl)}</text>`;
    if (r.on !== undefined) {
      s += `<rect x="282" y="${y - 5}" width="20" height="10" rx="5" fill="${r.on ? '#0a84ff' : '#3a4560'}"/><circle cx="${r.on ? 297 : 287}" cy="${y}" r="3.8" fill="#fff"/>`;
    } else if (r.arrow) {
      s += `<path d="M298 ${y - 3}l3 3-3 3" stroke="#8ea2c8" fill="none" stroke-width="1.2"/>`;
    }
  });
  return s + '</svg>';
}
const SHOTS = {
  en: {
    rp: () => psScreen({ crumb: ['Settings', 'System'], side: ['System Software', 'Power Saving', 'Remote Play', 'Language', 'Date and Time'], sel: 2, rows: [{ t: 'Enable Remote Play', on: true, hl: true }, { t: 'Link Device', arrow: true }, { t: 'Connection Information', arrow: true }] }),
    rest: () => psScreen({ crumb: ['Settings', 'System', 'Power Saving'], side: ['System Software', 'Power Saving', 'Remote Play', 'Language'], sel: 1, rows: [{ t: 'Stay Connected to the Internet', on: true, hl: true }, { t: 'Enable Turning On PS5 from Network', on: true, hl: true }, { t: 'Supply Power to USB Ports', arrow: true }] }),
    user: () => psScreen({ crumb: ['Settings', 'Users and Accounts', 'Other'], side: ['Account', 'Users', 'Other', 'Privacy'], sel: 2, rows: [{ t: 'Console Sharing and Offline Play', arrow: true }, { t: 'Enable', on: true, hl: true }, { t: 'Signed in: your PSN user', arrow: true }] }),
    link: () => psScreen({ crumb: ['Settings', 'System', 'Remote Play', 'Link Device'], side: ['System Software', 'Power Saving', 'Remote Play'], sel: 2, code: { label: 'Enter this number on the device', value: '1234 5678' } }),
  },
  ru: {
    rp: () => psScreen({ crumb: ['Настройки', 'Система'], side: ['Системное ПО', 'Энергосбережение', 'Дистанционная игра', 'Язык', 'Дата и время'], sel: 2, rows: [{ t: 'Включить дистанционную игру', on: true, hl: true }, { t: 'Связать устройство', arrow: true }, { t: 'Информация о подключении', arrow: true }] }),
    rest: () => psScreen({ crumb: ['Настройки', 'Система', 'Энергосбережение'], side: ['Системное ПО', 'Энергосбережение', 'Дистанционная игра', 'Язык'], sel: 1, rows: [{ t: 'Сохранять подключение к интернету', on: true, hl: true }, { t: 'Разрешить включение PS5 через сеть', on: true, hl: true }, { t: 'Питание USB-портов', arrow: true }] }),
    user: () => psScreen({ crumb: ['Настройки', 'Пользователи', 'Другое'], side: ['Учётная запись', 'Пользователи', 'Другое', 'Конфиденциальность'], sel: 2, rows: [{ t: 'Общий доступ к консоли и автономная игра', arrow: true }, { t: 'Включить', on: true, hl: true }, { t: 'Вход: ваш пользователь PSN', arrow: true }] }),
    link: () => psScreen({ crumb: ['Настройки', 'Система', 'Дистанционная игра', 'Связать'], side: ['Системное ПО', 'Энергосбережение', 'Дистанционная игра'], sel: 2, code: { label: 'Введите это число на устройстве', value: '1234 5678' } }),
  },
};

// ------------------------------------------------------------------ state
const S = { st: null, brain: null, idx: 0, maxIdx: 0, consoles: null, scanning: false, net: null, netBusy: false, mode: 'car', minutes: 10, agent: null, timers: {} };
const prog = () => (S.st && S.st.progress) || { checks: {} };
const R = () => (S.st && S.st.remote) || {};
const checks = () => prog().checks || {};
const PERMS = ['perm_rp', 'perm_rest', 'perm_user', 'perm_link'];

const STEPS = [
  { id: 'find', strict: false, ok: () => !!(S.st && (S.st.env_host || R().reachable)), render: renderFind, leave: () => {} },
  { id: 'permissions', strict: true, ok: () => PERMS.every((k) => checks()[k]), render: renderPerms, update: updatePerms },
  { id: 'psn', strict: false, ok: () => !!R().signed_in, render: renderPsn },
  { id: 'link', strict: false, ok: () => !!R().linked, render: renderLink, update: updateLink },
  { id: 'brain', strict: false, ok: () => !!(S.brain && S.brain.installed && S.brain.logged_in), render: renderBrain },
  { id: 'test', strict: false, ok: () => !!checks().test, render: renderTest, update: updateTest, leave: stopPreview },
  { id: 'play', strict: false, ok: () => !!prog().complete, render: renderPlay, leave: () => clearInterval(S.timers.agent) },
];
const PERM_IDX = 1;

async function saveProgress(patch) {
  const j = await api('/api/setup/progress', { body: patch });
  if (j.ok && S.st) { S.st.progress = j.progress; S.st.done = j.done; }
  return j;
}

// ------------------------------------------------------------------ chrome: rail, pills, footer
function renderRail() {
  const permOk = STEPS[PERM_IDX].ok();
  $('#rail').innerHTML = STEPS.map((s, i) => {
    const done = s.ok(), cur = i === S.idx;
    const locked = i > PERM_IDX && !permOk;
    return `<li class="${done ? 'done' : ''} ${cur ? 'current' : ''}"><button type="button" data-i="${i}" ${locked ? 'disabled' : ''} ${cur ? 'aria-current="step"' : ''}>
      <span class="dot">${done ? CHECK : i + 1}</span><span class="lbl"><b>${t('s_' + s.id)}</b><small>${t('s_' + s.id + '_d')}</small></span></button></li>`;
  }).join('');
  $('#railbar').style.transform = `scaleX(${(S.idx + 1) / STEPS.length})`;
}
// keep checkmarks from re-animating on every poll: only redraw rail when its signature changes
let railSig = '';
function syncRail() { const sig = lang + S.idx + STEPS.map((s) => +s.ok()).join(''); if (sig !== railSig) { railSig = sig; renderRail(); } }

function renderPills() {
  const r = R(), out = [];
  if (!S.st) out.push(['busy', 'PS5 …']);
  else if (!r.reachable) out.push(['bad', t('p_off')]);
  else if (r.power === 'on') out.push(['ok', (r.name ? r.name + ' · ' : '') + t('p_on')]);
  else out.push(['warn', t('p_rest')]);
  out.push(r.signed_in ? ['ok', t('p_psn', { u: r.signed_in })] : ['', t('p_nopsn')]);
  out.push(r.linked ? ['ok', t('p_linked')] : ['', t('p_nolink')]);
  const b = S.brain;
  if (!b) out.push(['busy', t('p_brain_chk')]);
  else if (!b.installed) out.push(['bad', t('p_brain_missing')]);
  else if (b.logged_in === false) out.push(['warn', t('p_brain_login')]);
  else out.push(['ok', t('p_brain')]);
  if (r.connected) out.push(['ok', t('p_conn')]);
  if (S.st && S.st.agent && S.st.agent.running) out.push(['ok', t('p_bot')]);
  const html = out.map(([k, txt]) => `<span class="pill ${k}"><i></i>${esc(txt)}</span>`).join('');
  if ($('#pills').innerHTML !== html) $('#pills').innerHTML = html;
}

function renderFoot() {
  const s = STEPS[S.idx], last = S.idx === STEPS.length - 1, ok = s.ok();
  const back = $('#back'), next = $('#next'), hint = $('#hint');
  back.textContent = t('back'); back.style.visibility = S.idx ? 'visible' : 'hidden';
  hint.textContent = '';
  if (last) { next.textContent = t('finishGo'); next.disabled = false; next.className = 'btn primary'; return; }
  if (ok) { next.textContent = t('next'); next.disabled = false; next.className = 'btn primary'; }
  else if (s.strict) { next.textContent = t('next'); next.disabled = true; next.className = 'btn primary'; hint.textContent = t('perm_hint'); }
  else { next.textContent = t('skip'); next.disabled = false; next.className = 'btn'; }
}

function chrome() { syncRail(); renderPills(); renderFoot(); }

function go(i) {
  i = Math.max(0, Math.min(STEPS.length - 1, i));
  if (i > PERM_IDX && !STEPS[PERM_IDX].ok()) i = PERM_IDX;
  const cur = STEPS[S.idx];
  if (cur && cur.leave) cur.leave();
  S.idx = i; S.maxIdx = Math.max(S.maxIdx, i);
  const el = $('#step');
  el.classList.remove('enter'); void el.offsetWidth; el.classList.add('enter');
  el.innerHTML = `<div class="kicker">${t('stepOf', { n: i + 1, total: STEPS.length })}</div>` + '<div id="body"></div>';
  STEPS[i].render($('#body'));
  chrome();
  saveProgress({ step: STEPS[i].id });
  if (matchMedia('(max-width: 860px)').matches) window.scrollTo({ top: 0, behavior: 'smooth' });
}

// ------------------------------------------------------------------ step 1: find
function renderFind(el) {
  el.innerHTML = `<h1>${t('find_t')}</h1><p class="lead">${t('find_l')}</p>
    <div id="found"></div>
    <div class="row" style="margin:12px 0 4px"><button class="btn sm" id="rescan" type="button">${t('rescan')}</button></div>
    <h2>${t('manual')}</h2>
    <form class="field" id="manual"><input class="input mono" id="ip" inputmode="decimal" autocomplete="off" spellcheck="false" placeholder="192.168.1.42" value="${esc((S.st && S.st.env_host) || '')}" aria-label="IP">
      <button class="btn" type="submit">${t('use')}</button></form>
    <p class="small muted" style="margin-top:8px">${t('ip_hint')}</p><div class="err" id="ip-err"></div>
    <h2>${t('net_t')}</h2><div id="net"></div>`;
  $('#rescan').onclick = scan;
  $('#manual').onsubmit = (e) => { e.preventDefault(); chooseHost($('#ip').value.trim()); };
  drawConsoles(); drawNet();
  if (!S.consoles) scan();
  if (!S.net && (S.st && (S.st.env_host || R().host))) runNet();
}
async function scan() {
  S.scanning = true; drawConsoles();
  const j = await api('/api/setup/discover');
  S.scanning = false; S.consoles = j.consoles || [];
  drawConsoles();
}
function drawConsoles() {
  const box = $('#found'); if (!box) return;
  if (S.scanning) { box.innerHTML = `<div class="scan"><span class="radar"></span>${t('scanning')}</div>`; return; }
  if (!S.consoles) { box.innerHTML = ''; return; }
  if (!S.consoles.length) { box.innerHTML = `<div class="empty">${t('none')}</div>`; return; }
  const cur = (S.st && S.st.env_host) || R().host;
  box.innerHTML = `<div class="consoles">${S.consoles.map((c) => `
    <button type="button" class="console ${c.ip === cur ? 'sel' : ''}" data-ip="${esc(c.ip)}">
      <span class="ico">${ICON.ps5}</span>
      <span class="meta"><b>${esc(c.name)}</b><span>${esc(c.ip)} · ${t('fw')} ${esc(fmtFw(c.firmware))}${c.app ? ' · ' + esc(c.app) : ''}</span></span>
      <span class="pill ${c.power === 'on' ? 'ok' : c.power === 'standby' ? 'warn' : ''}"><i></i>${pwLabel(c.power)}</span>
    </button>`).join('')}</div>`;
  box.querySelectorAll('.console').forEach((b) => (b.onclick = () => chooseHost(b.dataset.ip)));
}
async function chooseHost(ip) {
  const err = $('#ip-err'); if (err) err.textContent = '';
  if (!ip) return;
  const j = await api('/api/setup/host', { body: { host: ip } });
  if (!j.ok) { if (err) err.textContent = j.error || t('err'); return; }
  toast(t('saved', { h: ip }));
  if (S.st) S.st.env_host = ip;
  const inp = $('#ip'); if (inp) inp.value = ip;
  await refresh(); drawConsoles(); runNet(ip);
}
async function runNet(host) {
  S.netBusy = true; drawNet();
  const h = host || (S.st && S.st.env_host) || R().host || '';
  S.net = await api('/api/setup/network' + (h ? '?host=' + encodeURIComponent(h) : ''));
  S.netBusy = false; drawNet();
}
function drawNet() {
  const box = $('#net'); if (!box) return;
  const n = S.net;
  let html = `<div class="row"><button class="btn sm" id="netbtn" type="button" ${S.netBusy ? 'disabled' : ''}>${S.netBusy ? '<span class="spin"></span>' : ''}${t(n ? 'net_rerun' : 'net_run')}</button></div>`;
  if (n && n.ok !== false) {
    const p = n.ping || {}, kind = n.kind || 'unknown';
    const cls = (v, a, b) => v == null ? '' : v <= a ? 'ok' : v <= b ? 'warn' : 'bad';
    html += `<div class="tiles">
      <div class="tile ${kind === 'wifi' ? 'warn' : kind === 'ethernet' ? 'ok' : ''}"><small>${t('net_conn')}</small><b>${t(kind)}</b>${n.iface ? `<div class="small muted mono">${esc(n.iface)}${n.label ? ' · ' + esc(n.label) : ''}</div>` : ''}</div>
      <div class="tile ${cls(p.avg_ms, 5, 15)}"><small>${t('net_ping')}</small><b>${p.avg_ms ?? '—'}<em>${p.avg_ms != null ? 'ms' : ''}</em></b></div>
      <div class="tile ${cls(p.jitter_ms, 2, 5)}"><small>${t('net_jitter')}</small><b>${p.jitter_ms ?? '—'}<em>${p.jitter_ms != null ? 'ms' : ''}</em></b></div>
      <div class="tile ${cls(p.loss, 0, 2)}"><small>${t('net_loss')}</small><b>${p.loss ?? '—'}<em>${p.loss != null ? '%' : ''}</em></b></div></div>`;
    if (kind === 'wifi') html += banner('warn', t('net_wifi_t'), t('net_wifi'));
    if (!n.host) html += banner('info', '', t('net_nohost'));
    else if (!p.received) html += banner('info', '', t('net_noreply'));
    else if (n.verdict === 'warn' && kind !== 'wifi') html += banner('warn', t('net_bad_t'), t('net_bad'));
    else if (n.verdict === 'good') html += banner('ok', t('net_good_t'), t('net_good'));
  } else if (n) html += banner('bad', t('err'), esc(n.error || ''));
  box.innerHTML = html;
  $('#netbtn').onclick = () => runNet();
}

// ------------------------------------------------------------------ step 2: permissions
function renderPerms(el) {
  const items = [
    ['perm_rp', 'rp', 'rp'], ['perm_rest', 'rest', 'rest'], ['perm_user', 'user', 'user'], ['perm_link', 'link', 'link'],
  ];
  el.innerHTML = `<h1>${t('perm_t')}</h1><p class="lead">${t('perm_l')}</p><div class="checklist">${items.map(([key, k, shot]) => `
    <div class="item ${checks()[key] ? 'on' : ''}" data-k="${key}">
      <div class="body">
        <label class="tick"><input type="checkbox" ${checks()[key] ? 'checked' : ''} data-k="${key}"><span class="box">${CHECK}</span>
          <span><b>${t(k + '_t')}</b></span></label>
        <div class="path">${t(k + '_p').map((p, i) => (i ? '<i>›</i>' : '') + `<span>${esc(p)}</span>`).join('')}</div>
        <p class="small muted">${t(k + '_d')}</p>
        <div class="vslot" data-v="${key}"></div>
        ${k === 'user' ? `<details><summary>${t('user_err_t')}</summary>${t('user_err')}</details>` : ''}
      </div>
      <div class="shot" aria-hidden="true">${SHOTS[lang][shot]()}</div>
    </div>`).join('')}</div>`;
  el.querySelectorAll('input[type=checkbox]').forEach((cb) => (cb.onchange = async () => {
    cb.closest('.item').classList.toggle('on', cb.checked);
    if (S.st) S.st.progress.checks = { ...checks(), [cb.dataset.k]: cb.checked };
    chrome();
    await saveProgress({ checks: { [cb.dataset.k]: cb.checked } });
    chrome();
  }));
  updatePerms();
}
function updatePerms() {
  const r = R();
  const v = {
    perm_rp: r.reachable ? ['ok', t('v_reach')] : ['na', t('v_reach_no')],
    perm_rest: r.reachable && r.power === 'standby' ? ['ok', t('v_rest')] : ['na', r.reachable ? t('v_rest_on') : t('v_reach_no')],
    perm_user: r.signed_in ? ['ok', t('v_user', { u: r.signed_in })] : ['na', t('v_user_no')],
    perm_link: r.linked ? ['ok', t('v_linked')] : ['na', t('v_link_no')],
  };
  for (const [k, [cls, txt]] of Object.entries(v)) {
    const slot = document.querySelector(`.vslot[data-v="${k}"]`);
    const html = `<span class="verify ${cls}">${cls === 'ok' ? '✓' : '·'} ${esc(txt)}</span>`;
    if (slot && slot.innerHTML !== html) slot.innerHTML = html;
  }
}

// ------------------------------------------------------------------ step 3: PSN
function renderPsn(el, force) {
  const r = R();
  const a1 = '<a href="https://www.playstation.com/" target="_blank" rel="noopener">playstation.com</a>';
  const a2 = '<a href="https://ca.account.sony.com/api/v1/ssocookie" target="_blank" rel="noopener">ca.account.sony.com/api/v1/ssocookie</a>';
  let html = `<h1>${t('psn_t')}</h1><p class="lead">${t('psn_l')}</p>`;
  if (r.signed_in && !force) {
    html += `<div class="success"><span class="big">${CHECK}</span><div><b>${esc(t('psn_ok', { u: r.signed_in }))}</b><button class="btn sm ghost" id="psn-change" type="button" style="margin-top:6px;padding-left:0">${t('psn_change')}</button></div></div>`;
    el.innerHTML = html;
    $('#psn-change').onclick = () => renderPsn(el, true);
    return;
  }
  html += `<ol class="guide"><li><span>${t('psn_1', { a: a1 })}</span></li><li><span>${t('psn_2', { a: a2 })}</span></li><li><span>${t('psn_3')}</span></li></ol>
    <form class="field" id="psn-form"><input class="input mono" id="npsso" type="password" autocomplete="off" spellcheck="false" placeholder='${esc(t('psn_ph'))}' aria-label="NPSSO">
    <button class="btn primary" id="psn-btn" type="submit">${t('psn_btn')}</button></form>
    <div class="small muted" id="psn-len" style="margin-top:6px"></div><div class="err" id="psn-err"></div>
    ${banner('info', '', t('psn_safe'))}`;
  el.innerHTML = html;
  const inp = $('#npsso');
  const extract = (v) => { v = v.trim(); const m = v.match(/"npsso"\s*:\s*"([^"]+)"/); return m ? m[1] : v.replace(/^"|"$/g, ''); };
  inp.oninput = () => { $('#psn-len').textContent = t('psn_len', { n: extract(inp.value).length }); };
  $('#psn-form').onsubmit = async (e) => {
    e.preventDefault();
    const v = extract(inp.value);
    if (v.length !== 64) { $('#psn-err').textContent = t('psn_bad'); return; }
    $('#psn-err').textContent = '';
    const btn = $('#psn-btn'); busy(btn, true);
    const j = await api('/api/sign-in', { body: { npsso: v } });
    busy(btn, false);
    if (!j.ok) { $('#psn-err').textContent = j.error || t('err'); return; }
    inp.value = '';
    await refresh(); renderPsn(el); chrome();
  };
}

// ------------------------------------------------------------------ step 4: link
function renderLink(el, force) {
  const r = R();
  let html = `<h1>${t('lnk_t')}</h1><p class="lead">${t('lnk_l')}</p>`;
  if (r.linked && !force) {
    html += `<div class="success"><span class="big">${CHECK}</span><div><b>${esc(t('lnk_ok', { n: r.name || 'PS5' }))}</b><button class="btn sm ghost" id="lnk-again" type="button" style="margin-top:6px;padding-left:0">${t('lnk_again')}</button></div></div>`;
    el.innerHTML = html; $('#lnk-again').onclick = () => renderLink(el, true); return;
  }
  html += `<div id="lnk-warn"></div>
    <form id="lnk-form"><div class="pin" role="group" aria-label="PIN">${[...Array(8)].map((_, i) => (i === 4 ? '<span class="gap"></span>' : '') + `<input inputmode="numeric" maxlength="1" autocomplete="one-time-code" aria-label="${i + 1}" data-i="${i}">`).join('')}</div>
    <div class="row" style="margin-top:14px"><button class="btn primary" id="lnk-btn" type="submit" disabled>${t('lnk_btn')}</button></div></form>
    <div class="err" id="lnk-err"></div>
    <div class="item" style="margin-top:18px;grid-template-columns:1fr;max-width:420px"><div class="shot">${SHOTS[lang].link()}</div></div>`;
  el.innerHTML = html;
  const boxes = [...el.querySelectorAll('.pin input')];
  const val = () => boxes.map((b) => b.value).join('');
  const sync = () => { boxes.forEach((b) => b.classList.toggle('filled', !!b.value)); $('#lnk-btn').disabled = val().length !== 8; };
  boxes.forEach((b, i) => {
    b.oninput = () => { b.value = b.value.replace(/\D/g, '').slice(-1); if (b.value && boxes[i + 1]) boxes[i + 1].focus(); sync(); };
    b.onkeydown = (e) => { if (e.key === 'Backspace' && !b.value && boxes[i - 1]) { boxes[i - 1].focus(); boxes[i - 1].value = ''; sync(); e.preventDefault(); } };
    b.onpaste = (e) => { const d = (e.clipboardData.getData('text') || '').replace(/\D/g, '').slice(0, 8); if (!d) return; e.preventDefault(); d.split('').forEach((c, k) => { if (boxes[k]) boxes[k].value = c; }); (boxes[d.length] || boxes[7]).focus(); sync(); };
  });
  $('#lnk-form').onsubmit = async (e) => {
    e.preventDefault();
    const btn = $('#lnk-btn'); busy(btn, true); $('#lnk-err').textContent = '';
    const j = await api('/api/link', { body: { pin: val() } });
    busy(btn, false); sync();
    if (!j.ok) { $('#lnk-err').textContent = j.error || t('err'); return; }
    await refresh(); renderLink(el); chrome();
  };
  updateLink();
}
function updateLink() {
  const w = $('#lnk-warn'); if (!w) return;
  const r = R();
  const html = !r.signed_in ? banner('warn', '', t('lnk_need_psn')) : r.power !== 'on' ? banner('warn', '', t('lnk_need_on')) : '';
  if (w.innerHTML !== html) w.innerHTML = html;
}

// ------------------------------------------------------------------ step 5: brain
async function loadBrain() { S.brain = await api('/api/setup/brain'); chrome(); }
function renderBrain(el) {
  const b = S.brain;
  let html = `<h1>${t('br_t')}</h1><p class="lead">${t('br_l')}</p>`;
  if (!b) { el.innerHTML = html + `<div class="scan"><span class="radar"></span>${t('p_brain_chk')}</div>`; loadBrain().then(() => STEPS[S.idx].id === 'brain' && renderBrain(el)); return; }
  const status = !b.installed ? ['bad', t('br_missing')] : b.logged_in ? ['ok', t('br_ready')] : b.logged_in === false ? ['warn', t('br_login')] : ['warn', t('br_unknown')];
  const acct = b.auth ? [b.auth.email, b.auth.plan && b.auth.plan.toUpperCase(), b.auth.method].filter(Boolean).join(' · ') : '—';
  html += `<dl class="kv"><dt>${t('br_status')}</dt><dd><span class="pill ${status[0]}"><i></i>${status[1]}</span></dd>
    <dt>${t('br_path')}</dt><dd class="mono">${esc(b.path || '—')}</dd><dt>${t('br_version')}</dt><dd>${esc(b.version || '—')}</dd>
    <dt>${t('br_account')}</dt><dd>${esc(acct)}</dd></dl>`;
  if (b.installed && b.on_path === false) {
    const dir = (b.path || '').replace(/[\\/][^\\/]+$/, '');
    html += banner('warn', '', t('br_path_warn', { d: `<code>${esc(dir)}</code>` }));
  }
  if (!b.installed) {
    const c = b.commands || {};
    html += `<h2>${t('br_install_t')}</h2><p class="small muted">${t('br_install_l', { s: esc(c.shell || 'Terminal') })}</p>
      <div class="small" style="font-weight:600;margin-top:10px">${t('br_native')}</div>
      <div class="cmd"><code>${esc(c.native)}</code><button class="btn sm" type="button" data-copy="${esc(c.native)}">${ICON.copy}${t('copy')}</button></div>
      <div class="small" style="font-weight:600;margin-top:10px">${t('br_npm')}</div>
      <div class="cmd"><code>${esc(c.npm)}</code><button class="btn sm" type="button" data-copy="${esc(c.npm)}">${ICON.copy}${t('copy')}</button></div>
      <div class="row" style="margin-top:12px"><button class="btn primary" id="inst-native" type="button">${t('br_do_native')}</button>
      ${b.npm ? `<button class="btn" id="inst-npm" type="button">${t('br_do_npm')}</button>` : ''}</div>
      <div id="inst-msg" class="small" style="margin-top:8px"></div><div class="log" id="inst-log" hidden></div>`;
  } else {
    html += `<div class="row" style="margin-top:14px">
      ${b.logged_in ? '' : `<button class="btn primary" id="br-login" type="button">${t('br_signin')}</button>`}
      <button class="btn" id="br-recheck" type="button">${t('br_recheck')}</button>
      <button class="btn ghost" id="br-test" type="button">${t('br_test')}</button></div>
      ${b.logged_in ? '' : `<p class="small muted" style="margin-top:10px">${t('br_signin_h')}</p>`}
      <div id="br-msg" style="margin-top:6px"></div>`;
  }
  el.innerHTML = html;
  el.querySelectorAll('[data-copy]').forEach((x) => (x.onclick = () => copy(x.dataset.copy)));
  const recheck = async (btn) => { busy(btn, true); await loadBrain(); renderBrain(el); renderFoot(); };
  if ($('#br-recheck')) $('#br-recheck').onclick = (e) => recheck(e.currentTarget);
  if ($('#br-login')) $('#br-login').onclick = async () => { const j = await api('/api/setup/brain/login', { body: {} }); if (!j.ok) $('#br-msg').innerHTML = banner('warn', '', `<code>${esc(j.command || 'claude')}</code> — ${esc(j.error || '')}`); };
  if ($('#br-test')) $('#br-test').onclick = async (e) => {
    const btn = e.currentTarget; busy(btn, true);
    const j = await api('/api/setup/brain/check', { body: {} });
    busy(btn, false);
    $('#br-msg').innerHTML = j.ok ? banner('ok', t('br_test_ok', { ms: j.ms }), '') : banner('bad', '', esc(t('br_test_fail', { e: j.error || '' })));
    if (j.ok && S.brain) { S.brain.logged_in = true; chrome(); }
  };
  const inst = async (method) => {
    const j = await api('/api/setup/brain/install', { body: { method } });
    if (!j.ok) { $('#inst-msg').innerHTML = banner('bad', '', esc(j.error || t('err'))); return; }
    el.querySelectorAll('#inst-native,#inst-npm').forEach((x) => (x.disabled = true));
    $('#inst-msg').innerHTML = `<span class="spin" style="display:inline-block;vertical-align:-3px;margin-right:6px"></span>${t('br_installing')}`;
    const log = $('#inst-log'); log.hidden = false;
    clearInterval(S.timers.inst);
    S.timers.inst = setInterval(async () => {
      const s = await api('/api/setup/brain/install');
      if (!$('#inst-log')) { clearInterval(S.timers.inst); return; }
      log.textContent = (s.log || []).join('\n'); log.scrollTop = log.scrollHeight;
      if (!s.running && s.rc !== null && s.rc !== undefined) {
        clearInterval(S.timers.inst);
        if (s.rc === 0) { $('#inst-msg').textContent = t('br_inst_ok'); await loadBrain(); renderBrain(el); renderFoot(); }
        else { $('#inst-msg').innerHTML = banner('bad', '', t('br_inst_fail', { c: s.rc })); el.querySelectorAll('#inst-native,#inst-npm').forEach((x) => (x.disabled = false)); }
      }
    }, 1000);
  };
  if ($('#inst-native')) $('#inst-native').onclick = () => inst('native');
  if ($('#inst-npm')) $('#inst-npm').onclick = () => inst('npm');
}

// ------------------------------------------------------------------ step 6: test
const P = { on: false, url: null, frames: [], press: null, last: 0, timer: null, gotFrame: false };
function renderTest(el) {
  el.innerHTML = `<h1>${t('t_t')}</h1><p class="lead">${t('t_l')}</p>
    <div class="screen" id="scr"><span class="live-tag"><i></i>LIVE</span><img id="scr-img" alt=""><div class="ph" id="scr-ph">${t('t_wait')}</div></div>
    <div class="pad">${['CROSS', 'CIRCLE', 'TRIANGLE', 'SQUARE'].map((b) => `<button class="face" type="button" data-b="${b}" aria-label="${b}">${FACE[b]}</button>`).join('')}
      <span class="spacer" style="flex:1"></span>
      <button class="btn sm" id="t-wake" type="button">${t('t_wake')}</button>
      <button class="btn sm" id="t-conn" type="button">${t('t_connect')}</button></div>
    <div class="tiles" id="t-tiles"></div><div id="t-msg"></div>`;
  el.querySelectorAll('.face').forEach((b) => (b.onclick = () => pressBtn(b.dataset.b)));
  $('#t-conn').onclick = async (e) => {
    const btn = e.currentTarget;
    if (R().connected) { await api('/api/action/disconnect', { body: {} }); await refresh(); updateTest(); return; }
    busy(btn, true); const j = await api('/api/action/connect', { body: {} }); busy(btn, false);
    if (!j.ok) $('#t-msg').innerHTML = banner('warn', '', esc(j.error || t('err')));
    await refresh(); updateTest();
  };
  $('#t-wake').onclick = async (e) => { const btn = e.currentTarget; busy(btn, true); const j = await api('/api/action/wake', { body: {} }); busy(btn, false); toast(j.ok ? '✓' : (j.error || t('err'))); };
  P.on = true; P.frames = []; P.press = null; loopPreview(); updateTest();
}
async function loopPreview() {
  if (!P.on) return;
  const t0 = performance.now();
  let delay = 3000;
  try {
    const r = await fetch('/api/screen.jpg?w=960&t=' + Date.now(), { cache: 'no-store', headers: { 'X-Client': 'setup' } });
    if (r.ok && (r.headers.get('content-type') || '').includes('image')) {
      const blob = await r.blob();
      const ms = performance.now() - t0;
      P.frames.push({ ms, at: performance.now() }); if (P.frames.length > 12) P.frames.shift();
      const img = $('#scr-img');
      if (img && P.on) {
        const url = URL.createObjectURL(blob);
        img.onload = () => { if (P.url) URL.revokeObjectURL(P.url); P.url = url; img.classList.add('live'); $('#scr').classList.add('on'); $('#scr-ph').hidden = true; };
        img.src = url;
      }
      if (!P.gotFrame) { P.gotFrame = true; $('#t-msg').innerHTML = banner('ok', t('t_ok'), ''); if (!checks().test) { await saveProgress({ checks: { test: true } }); chrome(); } }
      delay = 250;
    } else {
      const j = await r.json().catch(() => ({}));
      const ph = $('#scr-ph'); if (ph) { ph.hidden = false; ph.textContent = j.error || t('t_wait'); }
      const img = $('#scr-img'); if (img) img.classList.remove('live');
      const sc = $('#scr'); if (sc) sc.classList.remove('on');
    }
  } catch (e) { const ph = $('#scr-ph'); if (ph) { ph.hidden = false; ph.textContent = t('offline'); } }
  updateTest();
  if (P.on) P.timer = setTimeout(loopPreview, delay);
}
function stopPreview() { P.on = false; clearTimeout(P.timer); if (P.url) { URL.revokeObjectURL(P.url); P.url = null; } P.gotFrame = false; }
async function pressBtn(b) {
  const t0 = performance.now();
  const j = await api('/api/press', { body: { buttons: [b], hold_ms: 80, gap_ms: 0 } });
  P.press = j.ok ? Math.round(performance.now() - t0) : null;
  if (!j.ok) $('#t-msg').innerHTML = banner('warn', '', esc(j.error || t('err')));
  else if (!checks().test) { await saveProgress({ checks: { test: true } }); chrome(); }
  updateTest();
}
function updateTest() {
  const box = $('#t-tiles'); if (!box) return;
  const f = P.frames, avg = f.length ? Math.round(f.reduce((a, x) => a + x.ms, 0) / f.length) : null;
  const span = f.length > 1 ? (f[f.length - 1].at - f[0].at) / 1000 : 0;
  const rate = span ? ((f.length - 1) / span).toFixed(1) : null;
  const age = R().frame_age_s;
  const cls = (v, a, b) => v == null ? '' : v <= a ? 'ok' : v <= b ? 'warn' : 'bad';
  box.innerHTML = `<div class="tile ${cls(avg, 120, 300)}"><small>${t('t_frame')}</small><b>${avg ?? '—'}<em>${avg != null ? 'ms' : ''}</em></b></div>
    <div class="tile ${cls(P.press, 150, 400)}"><small>${t('t_press')}</small><b>${P.press ?? '—'}<em>${P.press != null ? 'ms' : ''}</em></b></div>
    <div class="tile ${cls(age, 0.5, 2)}"><small>${t('t_age')}</small><b>${age ?? '—'}<em>${age != null ? 's' : ''}</em></b></div>
    <div class="tile"><small>${t('t_rate')}</small><b>${rate ?? '—'}<em>${rate ? 'fps' : ''}</em></b></div>`;
  const c = $('#t-conn'); if (c && !c.disabled) c.textContent = R().connected ? t('t_disconnect') : t('t_connect');
}

// ------------------------------------------------------------------ step 7: play
const MODES = [['car', 'car'], ['drive', 'wheel'], ['goto', 'pin'], ['mission', 'target']];
function renderPlay(el) {
  if (prog().mode) S.mode = prog().mode;
  if (prog().minutes) S.minutes = prog().minutes;
  const ov = location.origin + '/overlay';
  el.innerHTML = `<h1>${t('pl_t')}</h1><p class="lead">${t('pl_l')}</p>
    <div class="modes" role="radiogroup">${MODES.map(([m, ic]) => `<button type="button" role="radio" class="mode ${S.mode === m ? 'sel' : ''}" aria-checked="${S.mode === m}" data-m="${m}">
      <span class="mi">${ICON[ic]}</span><b>${t('m_' + m)}</b><span>${t('m_' + m + '_d')}</span></button>`).join('')}</div>
    <h2>${t('pl_dur')}</h2>
    <div class="range"><input type="range" min="1" max="60" step="1" id="mins" value="${S.minutes}" aria-label="${t('pl_dur')}"><output id="mins-o">${S.minutes} ${t('pl_min')}</output></div>
    <div class="row" style="margin-top:18px"><button class="btn primary" id="ag-btn" type="button">${t('pl_start')}</button><span class="small muted" id="ag-st"></span></div>
    <div class="err" id="ag-err"></div>
    <h2>${t('pl_log')}</h2><div class="log" id="ag-log"></div>
    <h2>${t('ov_t')}</h2><p class="small muted">${t('ov_l')}</p>
    <div class="cmd"><code>${esc(ov)}</code><button class="btn sm" type="button" id="ov-copy">${ICON.copy}${t('copy')}</button><a class="btn sm" href="/overlay" target="_blank" rel="noopener">${ICON.ext}${t('open')}</a></div>`;
  el.querySelectorAll('.mode').forEach((b) => (b.onclick = () => {
    S.mode = b.dataset.m;
    el.querySelectorAll('.mode').forEach((x) => { x.classList.toggle('sel', x === b); x.setAttribute('aria-checked', x === b); });
  }));
  $('#mins').oninput = (e) => { S.minutes = +e.target.value; $('#mins-o').textContent = `${S.minutes} ${t('pl_min')}`; };
  $('#ov-copy').onclick = () => copy(ov);
  $('#ag-btn').onclick = async (e) => {
    const btn = e.currentTarget; busy(btn, true); $('#ag-err').textContent = '';
    const running = S.agent && S.agent.running;
    const j = running ? await api('/api/setup/agent/stop', { body: {} }) : await api('/api/setup/agent/start', { body: { mode: S.mode, minutes: S.minutes } });
    busy(btn, false);
    if (!j.ok) $('#ag-err').textContent = j.error || t('err');
    else if (!running && !prog().complete) await saveProgress({ complete: true });
    S.agent = j; drawAgent(); chrome();
  };
  pollAgent(); clearInterval(S.timers.agent); S.timers.agent = setInterval(pollAgent, 1500);
}
async function pollAgent() { S.agent = await api('/api/setup/agent'); drawAgent(); }
function drawAgent() {
  const a = S.agent || {}, st = $('#ag-st'), btn = $('#ag-btn'), log = $('#ag-log');
  if (!st) return;
  const mm = (s) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
  st.textContent = a.running ? t('pl_running', { m: t('m_' + (a.mode || 'car')), t: mm(a.elapsed_s || 0) }) : (a.exit_code != null ? t('pl_exit', { c: a.exit_code }) : t('pl_idle'));
  if (!btn.disabled) { btn.textContent = a.running ? t('pl_stop') : t('pl_start'); btn.className = a.running ? 'btn danger' : 'btn primary'; }
  const text = (a.log || []).join('\n');
  if (log.textContent !== text) { const atEnd = log.scrollHeight - log.scrollTop - log.clientHeight < 30; log.textContent = text; if (atEnd) log.scrollTop = log.scrollHeight; }
}

// ------------------------------------------------------------------ boot / polling
async function refresh() {
  const j = await api('/api/setup/state');
  if (j.offline) { $('#pills').innerHTML = `<span class="pill bad"><i></i>${esc(t('offline'))}</span>`; return; }
  S.st = j;
  chrome();
  const s = STEPS[S.idx]; if (s && s.update) s.update();
}
function applyLang() {
  document.documentElement.lang = lang;
  document.querySelectorAll('[data-i18n]').forEach((n) => (n.textContent = t(n.dataset.i18n)));
  document.querySelectorAll('.seg button').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.lang === lang)));
  document.title = `GTA6 PS5 AI · ${t('setup')}`;
}
document.querySelectorAll('.seg button').forEach((b) => (b.onclick = () => {
  if (b.dataset.lang === lang) return;
  lang = b.dataset.lang; try { localStorage.setItem('ps5setup.lang', lang); } catch (e) { /* private mode */ }
  applyLang(); railSig = ''; go(S.idx);
}));
$('#back').onclick = () => go(S.idx - 1);
$('#next').onclick = async () => {
  if (S.idx === STEPS.length - 1) { await saveProgress({ complete: true }); toast(t('done_t')); setTimeout(() => (location.href = '/'), 600); return; }
  go(S.idx + 1);
};
$('#rail').onclick = (e) => { const b = e.target.closest('button[data-i]'); if (b && !b.disabled) go(+b.dataset.i); };

(async function boot() {
  applyLang();
  await refresh();
  const saved = STEPS.findIndex((s) => s.id === prog().step);
  S.idx = saved > 0 ? saved : 0;
  go(S.idx);
  loadBrain();
  setInterval(() => { if (!document.hidden) refresh(); }, 3000);
})();
})();
