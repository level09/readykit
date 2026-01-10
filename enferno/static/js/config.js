/**
 * ReadyKit - Central Configuration
 * Purple gradient color palette
 */

const config = {
    // Common Vue settings
    delimiters: ['${', '}'],

    // Vuetify configuration
    vuetifyConfig: {
        defaults: {
            VTextField: {
                variant: 'outlined'
            },
            VSelect: {
                variant: 'outlined'
            },
            VTextarea: {
                variant: 'outlined'
            },
            VCombobox: {
                variant: 'outlined'
            },
            VAutocomplete: {
                variant: 'outlined'
            },
            VChip: {
                size: 'small'
            },
            VCard: {
                elevation: 0
            },
            VBtn: {
                variant: 'elevated',
                size: 'small'
            },
            VDataTableServer: {
                itemsPerPage: 25,
                itemsPerPageOptions: [25, 50, 100]
            }
        },
        theme: {
            defaultTheme: localStorage.getItem('enferno-theme') || (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'),
            themes: {
                light: {
                    dark: false,
                    colors: {
                        // Purple gradient theme
                        primary: '#667eea',      // Purple-blue
                        secondary: '#764ba2',    // Purple
                        accent: '#06B6D4',       // Cyan
                        error: '#EF4444',        // Red
                        info: '#3B82F6',         // Blue
                        success: '#10B981',      // Emerald
                        warning: '#F59E0B',      // Amber
                        background: '#FFFFFF',   // White
                        surface: '#F9FBFD',      // Light Gray
                    }
                },
                dark: {
                    dark: true,
                    colors: {
                        // Dark purple palette
                        primary: '#818CF8',      // Lighter purple for dark mode
                        secondary: '#8B5CF6',    // Purple
                        accent: '#06B6D4',       // Cyan
                        error: '#EF4444',        // Red
                        info: '#3B82F6',         // Blue
                        success: '#10B981',      // Emerald
                        warning: '#F59E0B',      // Amber
                        background: '#0F172A',   // Slate 900
                        surface: '#1E293B',      // Slate 800
                        'surface-variant': '#334155',  // Slate 700
                        'on-background': '#F8FAFC',
                        'on-surface': '#E2E8F0',
                        'on-primary': '#FFFFFF',
                    }
                }
            }
        },
        icons: {
            defaultSet: 'mdi'  // Keep MDI as default, Tabler via ti- prefix
        }
    }
};
