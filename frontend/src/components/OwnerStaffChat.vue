<template>
  <div>
    <!-- Floating toggle -->
    <button
      ref="toggleBtnEl"
      type="button"
      class="ui-press fixed bottom-20 end-3 z-[2100] flex h-12 w-12 items-center justify-center rounded-full border border-slate-700/60 bg-slate-900/90 text-slate-200 shadow-lg backdrop-blur transition hover:border-amber-500/50 hover:text-amber-300 md:bottom-6"
      :aria-label="unread > 0 ? t('staffChat.titleWithUnread', { count: unread }) : t('staffChat.title')"
      :aria-expanded="isOpen"
      @click="toggle"
    >
      <AppIcon name="chat" class="h-5 w-5" aria-hidden="true" />
      <span
        v-if="unread > 0"
        class="absolute -end-1 -top-1 flex h-5 min-w-[1.25rem] items-center justify-center rounded-full bg-amber-500 px-1 text-[11px] font-bold tabular-nums text-slate-950"
        aria-hidden="true"
      >{{ unread > 99 ? t('staffChat.unreadCap') : unread }}</span>
    </button>

    <!-- Panel -->
    <Transition name="ui-fade">
      <div
        v-if="isOpen"
        class="fixed bottom-20 end-3 z-[2100] flex h-[28rem] max-h-[70vh] w-[min(22rem,calc(100vw-1.5rem))] flex-col overflow-hidden rounded-2xl border border-slate-700/60 bg-slate-900/95 shadow-2xl backdrop-blur md:bottom-6"
        role="dialog"
        aria-modal="true"
        aria-labelledby="staff-chat-title"
      >
        <!-- Panel header -->
        <div class="flex items-center justify-between gap-2 border-b border-slate-800 px-4 py-3">
          <div class="flex items-center gap-2 min-w-0">
            <span class="ui-live-dot bg-[var(--color-secondary)] shrink-0" aria-hidden="true" />
            <h2 id="staff-chat-title" class="truncate text-sm font-semibold text-white">{{ t("staffChat.title") }}</h2>
          </div>
          <button
            ref="closeBtnEl"
            type="button"
            class="ui-press ui-touch-target flex shrink-0 items-center justify-center rounded-lg px-1.5 text-slate-400 transition hover:text-white"
            :aria-label="t('common.close')"
            @click="close"
          >
            <AppIcon name="close" class="h-4 w-4" aria-hidden="true" />
          </button>
        </div>

        <!-- Message list -->
        <!-- TODO: requires logic change — add loading skeleton and error state once useStaffChat exposes loading/error -->
        <div ref="listEl" role="log" aria-labelledby="staff-chat-title" class="flex-1 overflow-y-auto px-3 py-3">
          <div v-if="!messages.length" class="ui-empty-state text-center p-5 space-y-1">
            <p class="text-sm font-semibold text-slate-100">{{ t("staffChat.emptyTitle") }}</p>
            <p class="text-xs text-slate-400">{{ t("staffChat.empty") }}</p>
          </div>
          <ul v-else class="space-y-2">
            <li
              v-for="(m, index) in messages"
              :key="m.id"
              class="ui-reveal rounded-xl border border-slate-800 bg-slate-950/50 px-3 py-2"
              :style="{ '--ui-delay': `${Math.min(index, 9) * 28}ms` }"
            >
              <div class="flex items-baseline justify-between gap-2">
                <span class="truncate text-xs font-semibold text-amber-300">{{ m.author_name || t("staffChat.someone") }}</span>
                <span class="shrink-0 tabular-nums text-[10px] text-slate-500">{{ formatTime(m.created_at) }}</span>
              </div>
              <p class="mt-0.5 whitespace-pre-wrap break-words text-sm text-slate-200">{{ m.body }}</p>
            </li>
          </ul>
        </div>

        <!-- Compose form -->
        <form class="flex items-center gap-2 border-t border-slate-800 px-3 py-2.5" @submit.prevent="onSend">
          <label for="staff-chat-input" class="sr-only">{{ t('staffChat.inputLabel') }}</label>
          <input
            id="staff-chat-input"
            v-model="draft"
            type="text"
            maxlength="1000"
            :placeholder="t('staffChat.placeholder')"
            :disabled="sending"
            class="ui-input ui-touch-target flex-1 text-sm"
          />
          <p class="sr-only" aria-live="polite" aria-atomic="true">{{ sending ? t("staffChat.sending") : "" }}</p>
          <button type="submit" class="ui-btn-primary ui-press shrink-0 text-sm" :disabled="sending || !draft.trim()">
            {{ t("staffChat.send") }}
          </button>
        </form>
      </div>
    </Transition>
  </div>
</template>

<script setup>
import { nextTick, onMounted, ref, watch } from "vue";

import AppIcon from "./AppIcon.vue";
import { useI18n } from "../composables/useI18n";
import { useStaffChat } from "../composables/useStaffChat";
import { useToastStore } from "../stores/toast";

const { t, currentLocale } = useI18n();
const toast = useToastStore();
const { messages, unread, isOpen, load, send, open, close } = useStaffChat();

const draft = ref("");
const sending = ref(false);
const listEl = ref(null);
const closeBtnEl = ref(null);
const toggleBtnEl = ref(null);

const toggle = () => (isOpen.value ? close() : open());

const scrollToBottom = () => {
  nextTick(() => {
    if (listEl.value) listEl.value.scrollTop = listEl.value.scrollHeight;
  });
};

const onSend = async () => {
  const text = draft.value.trim();
  if (!text || sending.value) return;
  sending.value = true;
  const ok = await send(text);
  sending.value = false;
  if (ok) {
    draft.value = "";
    scrollToBottom();
  } else {
    toast.show(t("staffChat.sendFailed"), "error");
  }
};

const formatTime = (iso) => {
  try {
    return new Intl.DateTimeFormat(currentLocale.value, { hour: "2-digit", minute: "2-digit" }).format(new Date(iso));
  } catch {
    return "";
  }
};

watch(() => messages.value.length, () => isOpen.value && scrollToBottom());
watch(isOpen, (open_) => {
  if (open_) {
    scrollToBottom();
    nextTick(() => closeBtnEl.value?.focus());
  } else {
    nextTick(() => toggleBtnEl.value?.focus());
  }
});

onMounted(load);
</script>
