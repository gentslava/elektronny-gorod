// Мастер установки: чистая логика «ответы → персональный план».
// UI рендерит вопросы и план, вся ветвящаяся логика — здесь (тестируется vitest).

import { project } from "./project";

export type WizardAnswers = {
  hasHA?: "yes" | "no";
  hasHACS?: "yes" | "no" | "what";
  wantAudio?: "yes" | "no";
  wantTalk?: "yes" | "no";
  hasHTTPS?: "yes" | "no" | "dontknow";
  wantRtsp?: "yes" | "no";
};

export interface WizardQuestion {
  id: keyof WizardAnswers;
  title: string;
  hint?: string;
  options: { value: string; label: string }[];
  /** Показывать ли вопрос при текущих ответах. */
  visible: (a: WizardAnswers) => boolean;
}

export const QUESTIONS: WizardQuestion[] = [
  {
    id: "hasHA",
    title: "Home Assistant уже установлен?",
    hint: "Это бесплатная система умного дома, в которую встраивается интеграция.",
    options: [
      { value: "yes", label: "Да" },
      { value: "no", label: "Ещё нет" },
    ],
    visible: () => true,
  },
  {
    id: "hasHACS",
    title: "HACS установлен?",
    hint: "HACS — магазин сообщества, через него ставится интеграция.",
    options: [
      { value: "yes", label: "Да" },
      { value: "no", label: "Нет" },
      { value: "what", label: "Не знаю, что это" },
    ],
    visible: (a) => a.hasHA === "yes",
  },
  {
    id: "wantAudio",
    title: "Нужен звук с камер и низкая задержка?",
    options: [
      { value: "yes", label: "Да" },
      { value: "no", label: "Пока достаточно видео" },
    ],
    visible: () => true,
  },
  {
    id: "wantTalk",
    title: "Хотите отвечать на звонок и говорить с гостем?",
    hint: "Экран вызова: видео и звук гостя, ответ, микрофон, открытие двери.",
    options: [
      { value: "yes", label: "Да" },
      { value: "no", label: "Достаточно видео и открытия двери" },
    ],
    visible: () => true,
  },
  {
    id: "hasHTTPS",
    title: "Home Assistant открывается по HTTPS?",
    hint: "Браузер отдаёт микрофон только защищённому адресу (https:// или localhost).",
    options: [
      { value: "yes", label: "Да" },
      { value: "no", label: "Нет" },
      { value: "dontknow", label: "Не знаю" },
    ],
    visible: (a) => a.wantTalk === "yes",
  },
  {
    id: "wantRtsp",
    title: "Нужны потоки камер вне Home Assistant (NVR, медиаплеер)?",
    options: [
      { value: "yes", label: "Да" },
      { value: "no", label: "Нет" },
    ],
    visible: () => true,
  },
];

export interface PlanStep {
  title: string;
  detail: string;
  link?: { href: string; label: string };
  optional?: boolean;
}

export interface WizardPlan {
  steps: PlanStep[];
  unlocks: string[];
  notes: string[];
  /** Что можно смело пропустить. */
  skipped: string[];
}

export function visibleQuestions(a: WizardAnswers): WizardQuestion[] {
  return QUESTIONS.filter((q) => q.visible(a));
}

export function isComplete(a: WizardAnswers): boolean {
  return visibleQuestions(a).every((q) => a[q.id] !== undefined);
}

export function buildPlan(a: WizardAnswers): WizardPlan {
  const steps: PlanStep[] = [];
  const unlocks: string[] = [];
  const notes: string[] = [];
  const skipped: string[] = [];

  if (a.hasHA === "no") {
    steps.push({
      title: "Установите Home Assistant",
      detail:
        "Подойдёт мини-ПК, Raspberry Pi или виртуальная машина. После установки вернитесь к этому мастеру — дальнейшие шаги не изменятся.",
      link: { href: project.haInstallDocs, label: "Официальная инструкция" },
    });
  }

  if (a.hasHA === "no" || a.hasHACS === "no" || a.hasHACS === "what") {
    steps.push({
      title: "Установите HACS",
      detail:
        a.hasHACS === "what"
          ? "HACS — каталог интеграций сообщества внутри Home Assistant. Ставится один раз, дальше всё обновляется из интерфейса."
          : "Один раз выполните установку HACS по официальной инструкции — дальше всё обновляется из интерфейса.",
      link: { href: project.hacsDocs, label: "Инструкция HACS" },
    });
  }

  steps.push({
    title: "Добавьте интеграцию в HACS",
    detail:
      "Кнопка откроет ваш Home Assistant с уже подставленным репозиторием. Установите интеграцию и перезапустите Home Assistant.",
    link: { href: project.hacsDeepLink, label: "Открыть в HACS" },
  });

  steps.push({
    title: "Подключите аккаунт оператора",
    detail:
      "Настройки → Устройства и службы → Добавить интеграцию → «Электронный город». Войдите по SMS-коду или паролю и выберите договоры. Логин и код вводятся только внутри вашего Home Assistant — сайт их не видит.",
    link: { href: project.configFlowDeepLink, label: "Открыть настройку" },
  });

  if (a.wantAudio === "yes" || a.wantRtsp === "yes") {
    steps.push({
      title: "Включите go2rtc для потоков",
      detail:
        "В Home Assistant 2024.11+ go2rtc уже встроен. В настройках интеграции выберите передачу потока через go2rtc — камеры получат звук и меньшую задержку.",
      link: { href: project.go2rtc, label: "Про go2rtc" },
    });
  } else {
    skipped.push("go2rtc — можно добавить позже, когда захочется звук с камер.");
  }

  if (a.wantTalk === "yes") {
    if (a.hasHTTPS !== "yes") {
      steps.push({
        title: "Настройте HTTPS-доступ",
        detail:
          a.hasHTTPS === "dontknow"
            ? "Откройте Home Assistant и посмотрите на адресную строку: замочек и https:// — значит всё готово. Если нет — подойдёт Home Assistant Cloud (Nabu Casa) или собственный reverse-proxy."
            : "Для микрофона браузеру нужен защищённый адрес: Home Assistant Cloud (Nabu Casa) или собственный reverse-proxy с сертификатом.",
      });
    }
    steps.push({
      title: "Соберите экран вызова",
      detail:
        "Добавьте Lovelace-ресурс карточки, подключите готовые blueprint-ы — пуш будет открывать экран с видео, ответом, микрофоном и открытием двери.",
      link: { href: project.callScreenDocs, label: "Пошаговая инструкция" },
    });
    unlocks.push("Ответ на вызов и разговор с гостем из Home Assistant");
  } else {
    skipped.push(
      "Экран вызова и микрофон — продвинутый слой, его можно включить в любой момент.",
    );
  }

  if (a.wantRtsp === "yes") {
    steps.push({
      title: "Опубликуйте камеры по RTSP",
      detail:
        "В настройках интеграции включите «Публиковать включённые камеры для внешнего RTSP». Адреса появятся в сущности «Опубликованные RTSP-потоки». Доступ из сети, firewall и VPN — зона вашей ответственности.",
      optional: true,
    });
    unlocks.push("Стабильные RTSP-адреса для NVR и медиаплееров");
  }

  steps.push({
    title: "Соберите первую автоматизацию",
    detail:
      "Начните с пуша о звонке с кадром камеры — готовый YAML лежит в библиотеке сценариев на этой странице.",
    link: { href: "#automations", label: "К библиотеке автоматизаций" },
  });

  unlocks.unshift(
    "Видео домофона и камер в Home Assistant",
    "Открытие двери из интерфейса и автоматизаций",
    "Событие звонка в реальном времени",
    "История принятых и пропущенных вызовов",
    "Баланс и режим «Не беспокоить»",
  );
  if (a.wantAudio === "yes") unlocks.push("Звук с камер через go2rtc");

  notes.push(
    "«Электронный город» и «Дом.ру» работают одинаково — оператора выбирать не нужно, а несколько аккаунтов и договоров живут в одной установке.",
    "Обновления приходят через HACS. После обновления перенастраивать интеграцию не нужно.",
  );

  return { steps, unlocks, notes, skipped };
}
