# Электронный город 3.7.2 — гостевой доступ, APK diff против 3.6.6

Status: Completed (static analysis; runtime capture не снимался)

Date: 2026-10-05 Scope: «Электронный город» (`com.electronnijgorod.novosibirsk`), функция «Гостевой доступ». Для сравнения — «Мой Дом» 9.10.0 / 9.11.0 (`ru.inetra.intercom`).

Процедура — [`.agents/commands/analyze-apk.md`](../../.agents/commands/analyze-apk.md), скрипты — [`research/scripts/apk/`](../scripts/apk/).

🔴 **ADR-0006.** Всё ниже — статическое доказательство из бинарника: клиент **умеет** так позвать. Что сервер отвечает, какие значения допустимы и какие поля обязательны, отсюда не следует. HAR этого приложения через MITM снять нельзя (WAF по JA3, см. [`api-reference.md`](../../docs/architecture/api-reference.md) «Backends — separate ecosystems»).

## Artifact verification

| Что | Значение | Откуда |
|---|---|---|
| `package` | `com.electronnijgorod.novosibirsk` | манифест base APK (`apktool d -s`) |
| `versionName` | `3.7.2` | манифест base APK; сошлось с карточкой RuStore |
| `versionCode` | `406` | манифест base APK; сошлось с `verCode` в RuStore. Схема «Мой Дом» (`major·10⁷+…`) к этому приложению не относится, тут сквозной счётчик |
| `targetSdk` | `36` | манифест |
| `minSdk` | `24` в файле | свойство варианта, не приложения (ловушка из [`9.10.0-analysis.md`](9.10.0-analysis.md)); с устройства не снимался |
| Подписант SHA-256 | `42b32c89…de74a54` | `apk-cert.py` на base `.apk` из XAPK: подпись v2 и дайджест содержимого сходятся |
| Сверка подписанта | **совпал** с `eg-3.6.6-original.apk` | `apk-cert.py eg-3.6.6-original.apk <3.7.2 base>` → «подписант один и тот же» |
| Дата | 28 сентября 2026 | RuStore — дата публикации **в RuStore** |

Попутный факт: это тот же отпечаток, что зафиксирован эталоном «Мой Дом» в [`README.md`](README.md). `apk-cert.py ru.inetra.intercom.apk(9.11.0) <ЭГ 3.7.2 base>` тоже отвечает «подписант один и тот же». Оба приложения подписаны одним ключом, так что эталон `42b32c89…` подходит для обоих. Сплит `config.armeabi_v7a.apk` подписан тем же ключом.

Файл: XAPK с apkcombo (pureapk), вариант `3.7.2 (406)`, 52 660 729 байт, совпало с `s=` в метаданных ссылки. Лежит в `research/apk/eg-3.7.2-original.xapk` (gitignored). Был ещё вариант на 59 185 627 байт под тем же `versionCode`; его не скачивали.

Отклонения от процедуры:
- Шаг 2: в сессии не было Playwright MCP. Файл скачан локальным Playwright из npx-кэша через системный Chrome (не headless, профиль в scratchpad). Сценарий тот же: список `a.variant`, затем переход браузером прямо на файловый URL из `u=`. В `.playwright-mcp/` файл не попадал, он сохранён через событие `download`.
- Шаг 3: проверялся base `.apk` из распакованного XAPK, а не сам контейнер.

## Что изменилось 3.6.6 → 3.7.2

### Инструменты процедуры здесь дают ложный ответ, и это надо знать

**`apk-endpoints.py` молча пропускает всю функцию.** Регулярка `ENDPOINT` берёт только пути, начинающиеся с `api/` или `rest/`. Диф 3.6.6 → 3.7.2 показал «добавлено 0, удалено 0» (19 путей в обеих версиях). А в 3.7.2 добавились 5 базовых URL и 23 пути вида `v1/rpc/…`, `v1/rest/…`, `rpc/guest/…`, `rpc/v1/…`. У ЭГ сервис зашит в базовый URL (`…/api/ntk-guests/`), а путь интерфейса начинается с `v1/`. Ловить такие вещи можно только полным списком строк dex: `comm -13` строк 3.6.6 и 3.7.2, затем фильтр по `https://` и `guest|invite`.

**`apk-contract.py` завершается ошибкой, причём по трём независимым причинам.** Ни одна из них не про переименование аннотаций:

1. `RequestFactory найден, но таблица аннотаций неполная: нет DELETE, GET, …, @HTTP`. Retrofit в этой сборке **не обфусцирован**, и jadx пишет вызов без получателя: `parseHttpMethodAndPath("DELETE", ((DELETE) annotation).value(), false)` (`retrofit2/RequestFactory.java:191-222`). `RF_VERB` и `RF_HTTP` требуют получателя с точкой перед вызовом (`[\w.]+\.\w+\(`), это форма обфусцированных сборок «Мой Дом». Поэтому ни одна ветка не распознаётся.
2. Если разрешить вызов без получателя, ошибка меняется на «ни одного Retrofit-вызова не распознано». `full()` достраивает имя без точки пакетом самого `RequestFactory`. Для 9.11.0 это верно (всё в `defpackage`), но здесь получается `retrofit2.DELETE`, а аннотации импортированы из `retrofit2.http`. В итоге короткое `@POST` в интерфейсах не засчитывается.
3. Подстрока сервиса (`ntk-guests`, `gatekeeper`) встречается только в `BuildConfig`, а не в путях интерфейсов. Искать надо по пути (`v1/rpc/`, `rpc/guest/`, `getGuestDevices`).

Плюс ограничение DTO-части. Скрипт ищет DTO с суффиксом `Raw` и Moshi-адаптеры, а ЭГ сериализует Jackson'ом: `JacksonConverterFactory.create(ExtensionsKt.jacksonObjectMapper())`, `app/backend/BaseApiFactoryImpl.java:36`. Имена на проводе тут — это имена Kotlin-свойств, кроме переопределённых `@JsonProperty` на параметрах конструктора и полей с `@JsonIgnore`. Они сняты вручную по классам DTO.

Первые две причины исправлены в самом скрипте: вызов без получателя разрешён, имя без точки разрешается через импорты `RequestFactory`. Теперь по `rpc/createInvite` он выдаёт контракт `GuestAccessApi`; на «Мой Дом» 9.10.0 и 9.11.0 вывод не изменился. Третья причина — подстрока сервиса в `BuildConfig`, а не в путях — свойство приложения: искать надо по пути (`rpc/createInvite`), а не по имени сервиса. Имена полей Jackson-DTO скрипт не разбирает — они сняты вручную.

### Новые базовые URL (все — `my.2090000.ru`)

`app/BuildConfig.java:22-28`:

| Константа | URL | Кто ходит |
|---|---|---|
| `NTK_GUESTS_API_URL` | `https://my.2090000.ru/api/ntk-guests/` | владелец: `GuestAccessApi` (`OwnerGuestAccessRepositoryImpl.java:60`) |
| `NTK_GUESTS_SELF_API_URL` | `https://my.2090000.ru/api/guests/` | гость: `GuestsApi`, `GuestSelfApi` (`GuestsSelfRepositoryImpl.java:74,83`) |
| `NTK_GUESTS_SELF_EQUIPMNET_API_URL` | `https://my.2090000.ru/api/guests/equipment/` | гость: `GuestNtkEquipmentApi` (`NtkEquipmentRepositoryImpl.java:158`) |
| `NTK_LK_GATEKEEPER_URL` | `https://my.2090000.ru/api/gatekeeper/` | гость, без авторизации: `GuestGatekeeperApi` (`GuestGatekeeperRepositoryImpl.java:46`, `buildNoAuth`) |
| `NTK_PHONE_VERIFICATION_URL` | `https://my.2090000.ru/api/phoneverification/` | гость при регистрации: `PhoneVerification` (`PhoneVerificationRepositoryImpl.java:28`) |

Ни одной строки `proptech` в dex 3.7.2 и в сплитах нет. Все 59 совпадений по `inetra` — ложные подстроки (`combineTransform`, `AffineTransform`). В 3.6.6 строк с `guest` в dex — 0.

### Авторизация

Общий перехватчик: `app/backend/InterceptorImpl.intercept`. Обычный jadx его не декомпилировал, разобран в режиме `-m simple`. Он ставит `Authorization: Bearer <token>`, а если запрос помечен `Authorization: no-auth`, снимает заголовок. Ещё он добавляет `ntk-user-agent`, `Content-Type: application/json;charset=UTF-8` и `Accept: application/json`. User-Agent: `MLK/%s (build: %d; os: Android %s; abi: %s; sdk: %d; model: %s)`, `GuestsApiFactoryImpl.java:193`.

Токен выбирает `AuthDataServiceImpl.fetchAuthToken` (`:101-121`):
- **владелец** — обычный `authtoken` аккаунта из `AccountManager`. Это существующий Keycloak-вход ЭГ, тот же, которым ходят остальные запросы на `my.2090000.ru/api/`;
- **гость** (`AccountHelper.isGuest`, `:107`) — JWT из `GuestTokenManager.getOrCreateGuestToken`. Его выдаёт `gatekeeper`: `POST rpc/guest/v1/createToken {userId, phone}` → `{jwt}` (`GuestTokenManager.java:169-171`). Проверка — `POST rpc/guest/v1/checkToken {jwt}` → `{verified}` (`:148`). На 401 или `verified=false` токен пересоздаётся. Пароля у гостя нет, гость — отдельная сущность `user` со своим `id` (см. регистрацию ниже). В Keycloak гость не входит.

Маркеры в заголовках: `HEADER_NO_AUTH = "Authorization: no-auth"` (`GuestsApiKt.java:9`) — на `checkInvite`, `createUser` и обоих вызовах gatekeeper. `HEADER_ACCESS_TOKEN_STUB = "accesstoken: none"` (`GuestNtkEquipmentApiKt.java:9`) — на всех вызовах `guests/equipment/`.

### Контракт (static-only)

Пути относительные к базовому URL из таблицы выше. Имена полей — **на проводе** (Jackson). Поле, переименованное `@JsonProperty`, показано как `провод ← kotlin`.

#### Владелец: `…/api/ntk-guests/` — `app/backend/GuestAccessApi.java:22-33`

| Действие | Вызов | Тело / заголовки | Ответ |
|---|---|---|---|
| Создать приглашение с выбором объектов | `POST v1/rpc/createInvite` | `CreateInviteDto {accountId:int, HWID ← hwid:String, owner:String, devices:[int]}` | `CreateInviteResultDto {uuid, validUntil, qrcodeUrl, deeplink}` (строки) |
| Список гостей | `GET v1/rpc/getGuestsByOwner` | заголовок `accountid: <int>` | `[GuestDto]` |
| Редактировать доступ к объектам | `PATCH v1/rest/guest/{id}` | `UpdateGuestDto {devices:[String]}` | пусто (`Completable`) |
| Удалить гостя | `PATCH v1/rpc/disableGuest/{id}` | без тела | пусто |

`GuestDto` (`dto/guestaccess/GuestDto.java:163`): `id, user ← userId, guestName, ownerName, accountId, ownerHWID ← ownerHwid, devices:[GuestDeviceDto], isEnabled, createdAt, lastActivity`.
`GuestDeviceDto`: `cameraId:Long, deviceType:String, accessControlId:Long, cameraDeviceId:Long`.

Откуда значения (`ui/viewmodel/InviteGuestSelectObjectsViewModel.java`):
- `accountId` — имя аккаунта как число, то есть номер договора (`:616`). `HWID` — `IdsUtil.getDeviceId()` (`:631`). `owner` — ФИО владельца, а если его нет, имя аккаунта (`:632-644`).
- `devices` — отсортированные id устройств из **`ntk-video-equipment`** `rest/v1/devices` (`NtkEquipmentRepository.getAllDevicesByAccount`, `:292`), пересечённые с выбранными (`:627`). Список фильтруется так: в выбор попадают непубличные устройства категорий `ACCESS` и `CAMERAS` (`:344`). Отсюда фильтры «Все объекты / Доступ / Камеры» (`InviteObjectFilter.ALL/ACCESS/CAMERAS`, `:74-84`).
- Для `updateGuest` id переводятся в строки (`GuestAccessMapper.mapUpdateGuestDto`). При редактировании уже выданные объекты предвыбираются так: устройство совпадает по `deviceType`, `content.cameraId`, `accessControlId` и `cameraDeviceId` (`domain/model/DeviceModelKt.matchesGuestDevice`).

QR и ссылку строит **сервер**. Экран «Пригласить гостя» грузит картинку по `qrcodeUrl` через Picasso (`InviteGuestDoneFragment.java:229`), а «Поделиться» отправляет `deeplink` как `EXTRA_TEXT` (`:260`). Срок жизни приходит полем `validUntil`. Строки «30 минут» в ресурсах ЭГ нет, так что TTL задаёт сервер или контент сторис. **Status: unknown**, значение статикой не установить.

#### Гость: вход по QR или ссылке

Точка входа — deep link `mlk://invite/<uuid>` (`AndroidManifest.xml`: `GuestInstructionActivity`, intent-filter `scheme=mlk host=invite`). `uuid` — последний сегмент пути (`GuestInstructionActivity.java:131-143`). Сканер «Вход для гостей» просто открывает отсканированную строку как `ACTION_VIEW` (`GuestInstructionFragment.java:94`), так что QR несёт тот же deep link.

Последовательность (`ui/viewmodel/GuestAuthViewModel.java`):

1. `POST guests/ v1/rpc/checkInvite` без авторизации, `CheckInviteDto {userId:null, uuid}` → `CheckInviteResultDto {result:bool, message}` (`:171`).
2. Подтверждение телефона: `POST phoneverification/ v1/rpc/getPhoneCall {phone}` (flash call, `:234`) или `v1/rpc/getVerificationCode {phone}` (СМС, `:287`) → `{token}`. Затем `v1/rpc/verifyPhone {token, code, phone}` → `PhoneVerificationResult {isVerified, message, rejectReason}` (`:473-478`).
3. `POST guests/ v1/rest/user` без авторизации, `CreateUserBody {phone, HWID ← hwid, name}` → `CreateUserReply {id, token}` (`:474`, `:546`). Поле `inviteUuid` помечено `@JsonIgnore` и на провод не уходит.
4. `POST guests/ v1/rpc/checkInvite {userId, uuid}` (`:585`).
5. Если `result=true`: `POST guests/ v1/rest/guest` с `Bearer <token из шага 3>`, `CreateGuestBody {userId, inviteUUID}` → `CreateGuestReply {result, message, id}` (`:613`). Иначе: `GET guests/ v1/rest/invite/{uuid}` → `InviteInfoDto {uuid, accountId, validUntil, usedAt}` (`:627`). Если `usedAt` не пуст или срок истёк — ошибка «Приглашение уже было использовано…». Если нет — восстановление существующего гостя через `GET v1/rpc/getGuestsByUser/{id}` (`:699`).
6. Сессия сохраняется в `AccountManager` как отдельный аккаунт `guest-…` с `IS_GUEST`, `GUEST_USER_ID`, `GUEST_ID`, `GUEST_INVITE_UUID`, `GUEST_PHONE` (`AuthDataServiceImpl.saveGuestToken`, `:130-166`). Дальше JWT берётся из gatekeeper (см. «Авторизация»).

#### Гость: что он может после входа

`…/api/guests/` — `GuestSelfApi`: `GET v1/rest/guest/{id}` → `GuestDto`, `PATCH v1/rpc/disableGuest/{id}` (удалить себя).

`…/api/guests/equipment/` — `GuestNtkEquipmentApi.java:27-58`. У каждого вызова заголовки `accesstoken: none` и `accountid: <договор владельца>`:

| Вызов | Параметры |
|---|---|
| `POST rpc/v1/getGuestDevices` | тело `GetGuestDevicesBody {guestId, accountId}` → `[DeviceDto]` |
| `POST rpc/devices/v1/open` | query `deviceId`, тело `GuestOpenDeviceBody {deviceId}` |
| `GET rpc/devices/v1/translation?type=video` | query `deviceId` (+ `timestamp`, `tz` для архива) → `TranslationUrlDto {URL, type}` |
| `GET rpc/devices/v1/translation` | query `deviceId`, `type` (кадр) |
| `GET rest/v1/devices/{id}/archiveurl` | `timestamp`, `duration`, `tz`, `container` |
| `GET rest/v1/devices/{id}/cameraevents` | `lowerdate`, `upperdate`, `count` |
| `GET rest/v1/devices/changeMainState` | `deviceId`, `isMain` |

Это зеркало путей владельца из `ntk-video-equipment`, но под префиксом `guests/equipment/`. Отсюда «гость может открывать двери и смотреть камеры», и только выданные устройства (`getGuestDevices` по `guestId`).

### Это не подключаемая услуга, но доступ к ней обусловлен

В ЭГ 3.7.2 нет ни `managed_service`, ни `TEMP_PASS`, ни `ManagedServiceConnect*`: 0 совпадений в dex. У гостевых строк нет пары состояний `*_not_active_*` и кнопки «Подключить». Remote-config или feature-флага для гостей тоже нет.

Пункт меню «Гостевой доступ» показывается по условию (`ui/accountchange/AccountChangeFragment.java:368-433`). Нужно, чтобы на договоре была подписка (`GET user/v2/subscriptions/getAddressGroupedSubscriptions`, `UserApi.java:129`, эндпоинт есть и в 3.6.6) с `serviceId ∈ GUEST_ACCESS_SERVICE_IDS = {CAMERA_ACCESS=521, PASC=523}` (`app/backend/ServiceId.java:61`) и чтобы аккаунт не был юрлицом (`isCompany`). Иначе пункт скрыт. Получается, функция встроенная, но видна только на договорах с услугой доступа к камерам или с услугой `PASC`.

Экраны со скриншотов все есть в ресурсах. Все строки — с префиксами `guest_access__*`, `guest_invite_select_objects__*`, `guest_invite_done__*`, `guest_auth__*`, `guest_account__*`, всего 75 строк, в 3.6.6 их не было. По экранам:
- «Гостевой доступ»: `guest_access__main_title`, пустое состояние `guest_access__empty_list`, `guest_access__add_guest`;
- «Выбор объектов»: `…__title`, `…__filter_all/access/cameras`, `…__select_all`, `…__grant_access`, `…__send`;
- «Пригласить гостя»: `guest_invite__title`, `guest_invite_done__step_1/2`, `…__share_button`;
- «Гости» → пользователь: `guest_access__details_title/invited/last_activity/edit_access/delete_profile`;
- вход гостя: `toGuestInstructionText` «Вход для гостей», `guest_auth__*`.

## Сравнение с «Мой Дом» 9.10.0 / 9.11.0

| | ЭГ 3.7.2 «Гостевой доступ» | «Мой Дом» приглашение в дом (A-93) | «Мой Дом» `mh-temp-pass` (A-118) |
|---|---|---|---|
| Хост | `my.2090000.ru` | `myhome.proptech.ru` | `myhome.proptech.ru` |
| Создание | `POST ntk-guests/v1/rpc/createInvite {accountId, HWID, owner, devices}` | `POST api/mh-auth/mobile/v1/guests/link?placeId=&app=` → `{data}` | `POST api/mh-temp-pass/mobile/v1/rest/v1/temp-passes` с `ttl`, `accessControlIds` |
| Гранулярность | id устройств `ntk-video-equipment` (двери и камеры) | адрес целиком (`placeId`) | id `accessControl` (двери), без камер |
| Кто гость | отдельная учётка: `guests/v1/rest/user` + `v1/rest/guest`, JWT от `gatekeeper` | абонент на адресе с ролью «Гость»: `auth/v2/guests` (`GuestAuthRaw {phoneNumber, authCode, subscriberInvite, name, invitationSendType, appId, requestSms}`), принятие через `PUT rest/v1/subscriberinvites` | учётки нет, ссылка |
| Отзыв | `PATCH v1/rpc/disableGuest/{id}` | удаление с адреса | удаление пропуска (`temp-passes/{id}`) |
| Доступность | пункт меню при подписке 521/523 | встроено | `managed_service` `TEMP_PASS`, только если сервер прислал `feature` |

Совпадений по путям, хостам и именам DTO нет. Маркеры ЭГ (`ntk-guests`, `createInvite`, `getGuestsByOwner`, `disableGuest`, `getGuestDevices`, `checkInvite`, `gatekeeper`, `phoneverification`, `ownerHWID`, `2090000`) в dex «Мой Дом» 9.11.0 и в декомпиляте 9.10.0 встречаются 0 раз. В ЭГ, наоборот, нет `proptech`, `mh-auth`, `subscriberinvites`, `mh-temp-pass`.

**Скрытого кода «гость с выбором объектов» в «Мой Дом» 9.11.0 нет.** Все классы с `Guest`/`Invite` относятся к трём вещам:
- приглашение на адрес: `feature/guest/invite/…/InviteLinkRaw`, `InviteLinkResponseRaw`;
- вход гостя: `feature/auth/…/GuestAuthRaw`, `GuestTokenRaw`, `SubscriberInviteRaw`, `erid/api/InviteRaw`;
- события `guestAdded` / `guestDeleted`.

Ни в одном DTO из этой группы нет списка устройств. Единственное место в 9.11.0, где есть выбор объектов (`accessControlIds`), — это `mh-temp-pass` (`TempPassInfo`, `TempPassItemUi`, `CreateTempPassRequestRaw`) и `rest/v1/temporal-codes`. В ресурсах 9.11.0 нет ни одной строки экранов ЭГ: «Выбор объектов», «Выбрать все», «Отправить приглашение», «Приглашенных пока нет», «Редактировать доступ к объектам», «Гостевой доступ», «Вход для гостей», «Последняя активность». «Выдать доступ» там есть, но это кнопка промо временного пропуска (`access_keys_temp_pass_banner_button`, `temp_pass_promo_banner_button`).

Одна оговорка про общую лексику. В `GuestDeviceDto` и `DeviceDto` ЭГ есть поля `accessControlId` (в `DeviceDto` уже с 3.6.6) и `cameraDeviceId` (новое в 3.7.2). Слова совпадают со словарём proptech: `accesscontrols/{accessControlId}`. Совпадают ли сами id, по статике не установить, и на путь клиента это не влияет: клиент ЭГ шлёт их только на `my.2090000.ru`.

## Куда это ведёт

- **Ответ на гипотезу пользователя.** Наполовину верно. В ЭГ гостевой доступ с выбором объектов реализован целиком: и сторона владельца, и сторона гостя. Подключаемой услугой он не оформлен, но виден только при подписке 521/523. А вот «не доделано в „Мой Дом“» статика не подтверждает. Это разные функции за разными API-шлюзами (общий ли сервер за ними — см. живую проверку ниже). В «Мой Дом» свой законченный механизм — приглашение на адрес, без выбора объектов, а выбор дверей там живёт в отдельной услуге `TEMP_PASS`.
- **Для интеграции.** Повторить гостевой доступ ЭГ через `myhome.proptech.ru` нельзя: такого вызова у «Мой Дом» нет, а код интеграции повторяет «Мой Дом» (ADR-0006). Ближайший аналог на нашем хосте — `mh-temp-pass` (A-118). Клиент к `my.2090000.ru` — отдельный шлюз с Keycloak и anti-MITM WAF, вне скоупа.
- **Уверенность.** Высокая — в том, что пути клиентов не пересекаются: разные хосты, пути, DTO, модель гостя и способ авторизации, и всё это доказано строками и классами обеих сборок. Связаны ли сервисы `my.2090000.ru` с proptech на стороне сервера, статика не говорит — см. живую проверку ниже. Тоже неизвестно, какие TTL, обязательные поля и ответы у вызовов выше.
- **Инструменты.** На этом приложении `apk-endpoints.py` даёт ложное «изменений нет» (видит только пути с `api/` и `rest/`); `apk-contract.py` после правки пути находит, но DTO Jackson не разбирает. Ловушка записана в `research/scripts/apk/README.md`.
- [`api-reference.md`](../../docs/architecture/api-reference.md) не трогаем: всё статическое и относится к чужому API-шлюзу.

## Живая проверка хостов (2026-10-05)

Владелец считает, что «Мой Дом», «Умный Дом.ру» и ЭГ под Android и iOS ходят на один бэкенд с разными хостами. Проверено скриптом [`research/scripts/probe-hosts.py`](../scripts/probe-hosts.py) с HAR сессии эмулятора (контрольный запрос — 200). Только чтение; токен в вывод не попадает.

| Запрос | Ответ |
|---|---|
| `myhome.proptech.ru` `api/ntk-guests/…/getGuestsByOwner` с токеном | 404 «Страница не найдена» — тот же ответ, что на несуществующий путь |
| `my.2090000.ru` `rest/v3/subscriber-places` с токеном и без | 403 — тот же ответ, что на несуществующий путь |
| `my.2090000.ru` `api/ntk-guests/…/getGuestsByOwner` без токена | 400 |
| то же с мусорным токеном | 500 |
| то же с токеном «Мой Дом» | 500 — как с мусорным |

Оба хоста стоят за одним провайдером защиты (ServicePipe, AS201706), сертификаты разные (`*.proptech.ru` и `*.2090000.ru` на «Новотелеком»). «Мой Дом» и «Умный Дом.ру» под Android действительно ходят на один хост `myhome.proptech.ru`; iOS-сборки не проверялись.

**Вывод.** Снаружи это два API-шлюза с разными путями и разной авторизацией: шлюзы не пропускают пути друг друга, токены не взаимозаменяемы. Общий сервер за ними этим не опровергнут. Для интеграции разницы нет: гостевой доступ ЭГ требует токен ЭГ.
