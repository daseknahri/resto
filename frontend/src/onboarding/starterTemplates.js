// THEME_PRESETS labels are i18n keys, not display strings (A3-30): StepTheme
// renders t(preset.labelKey) so fr/ar UI no longer shows English preset names.
// The template-palette entries built by StepTheme.loadTemplatePalettes carry a
// pre-translated `label` instead; renderers must handle both shapes.
export const THEME_PRESETS = [
  { id: "amber-teal", labelKey: "stepTheme.presets.amberTeal", primary: "#0F766E", secondary: "#F59E0B" },
  { id: "charcoal-red", labelKey: "stepTheme.presets.charcoalRed", primary: "#334155", secondary: "#EF4444" },
  { id: "forest-lime", labelKey: "stepTheme.presets.forestLime", primary: "#166534", secondary: "#84CC16" },
  { id: "ocean-coral", labelKey: "stepTheme.presets.oceanCoral", primary: "#0C4A6E", secondary: "#FB7185" },
];
