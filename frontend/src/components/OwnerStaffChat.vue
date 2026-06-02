<template>
  <div>
    <!-- Floating toggle -->
    <button
      type="button"
      class="fixed bottom-20 right-3 z-[2100] flex h-12 w-12 items-center justify-center rounded-full border border-slate-700/60 bg-slate-900/90 text-slate-200 shadow-lg backdrop-blur transition hover:border-amber-500/50 hover:text-amber-300 md:bottom-6"
      :aria-label="t('staffChat.title')"
      @click="toggle"
    >
      <AppIcon name="chat" class="h-5 w-5" aria-hidden="true" />
      <span
        v-if="unread > 0"
        class="absolute -right-1 -top-1 flex h-5 min-w-[1.25rem] items-center justify-center rounded-full bg-amber-500 px-1 text-[11px] font-bold text-slate-950"
      >{{ unread > 99 ? "99+" : unread }}</span>
    </button>

    <!-- Panel -->
    <div
      v-if="isOpen"
      class="fixed bottom-20 right-3 z-[2100] flex h-[28rem] max-h-[70vh] w-[min(22rem,calc(100vw-1.5rem))] flex-col overflow-hidden rounded-2xl border border-slate-700/60 bg-slate-900/95 shadow-2xl backdrop-blur md:bottom-6"
      role="dialog"
      :aria-label="t('staffChat.title')"
    >
      <div class="flex items-center justify-between gap-2 border-b border-slate-800 px-4 py-3">
        <p class="text-sm font-semibold text-white">{{ t("staffChat.title") }}</p>
        <button type="button" class="rounded-lg p-1 text-slate-400 transition hover:text-white" :aria-label="t('common.close')" @click="close">
          <AppIcon name="close" class="h-4 w-4" aria-hidden="true" />
        </button>
      </div>

      <div ref="listEl" role="log" aria-live="polite" class="flex-1 space-y-2 overflow-y-auto px-3 py-3">
        <p v-if="!messages.length" class="py-8 text-center text-xs text-slate-500">{{ t("staffChat.empty") }}</p>
        <div v-for="m in messages" :key="m.id" class="rounded-xl border border-slate-800 bg-slate-950/50 px-3 py-2">
          <div class="flex items-baseline justify-between gap-2">
            <span class="truncate text-xs font-semibold text-amber-300">{{ m.author_name || t("staffChat.someone") }}</span>
            <span class="shrink-0 text-[10px] text-slate-500">{{ formatTime(m.created_at) }}</span>
          </div>
          <p class="mt-0.5 whitespace-pre-wrap break-words text-sm text-slate-200">{{ m.body }}</p>
        </div>
      </div>

      <form class="flex items-center gap-2 border-t border-slate-800 px-3 py-2.5" @submit.prevent="onSend">
        <input
          v-model="draft"
          type="text"
          maxlength="1000"
          :placeholder="t('staffChat.placeholder')"
          :aria-label="t('staffChat.title')"
          :disabled="sending"
          class="ui-input flex-1 py-2 text-sm"
        />
        <button type="submit" class="ui-btn-primary shrink-0 px-3 py-2 text-sm" :disabled="sending || !draft.trim()">
          {{ t("staffChat.send") }}
        </button>
      </form>
    </div>
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
watch(isOpen, (open_) => open_ && scrollToBottom());

onMounted(load);
</script>
