/**
 * ReadyKit - Central Configuration
 * Minimal monochrome palette with single accent color
 */

const config = {
    // Common Vue settings
    delimiters: ['${', '}'],

    // Vuetify configuration
    vuetifyConfig: {
        defaults: {
            VTextField: {
                variant: 'underlined'
            },
            VSelect: {
                variant: 'underlined'
            },
            VTextarea: {
                variant: 'underlined'
            },
            VCombobox: {
                variant: 'underlined'
            },
            VAutocomplete: {
                variant: 'underlined'
            },
            VChip: {
                size: 'small'
            },
            VCard: {
                elevation: 0
            },
            VBtn: {
                variant: 'flat'
            },
            VDataTableServer: {
                itemsPerPage: 25,
                itemsPerPageOptions: [25, 50, 100]
            }
        },
        theme: {
            defaultTheme: 'light',
            themes: {
                light: {
                    dark: false,
                    colors: {
                        primary: '#18181B',      // Zinc-900 — near-black
                        secondary: '#71717A',    // Zinc-500 — muted gray
                        accent: '#F97316',       // Orange-500 — warm CTA accent
                        error: '#EF4444',        // Red
                        info: '#3B82F6',         // Blue
                        success: '#10B981',      // Emerald
                        warning: '#F59E0B',      // Amber
                        background: '#FFFFFF',   // White
                        surface: '#FFFFFF',      // White (no tinted surface)
                    }
                }
            }
        },
        icons: {
            defaultSet: 'mdi'
        }
    }
};
