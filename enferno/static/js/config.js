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
            // Vuetify makes card-action buttons text by default; keep primary actions filled.
            VCardActions: {
                VBtn: {variant: 'flat'}
            },
            VTextField: {
                variant: 'outlined',
                density: 'comfortable'
            },
            VSelect: {
                variant: 'outlined',
                density: 'comfortable'
            },
            VTextarea: {
                variant: 'outlined',
                density: 'comfortable'
            },
            VCombobox: {
                variant: 'outlined',
                density: 'comfortable'
            },
            VAutocomplete: {
                variant: 'outlined',
                density: 'comfortable'
            },
            VChip: {
                size: 'small'
            },
            VCard: {
                elevation: 0
            },
            VBtn: {
                variant: 'flat',
                class: 'text-none'
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
        // Vuetify's built-in icons (sort, pagination, checkboxes) default to MDI; map them to Tabler
        icons: {
            defaultSet: 'ti',
            sets: {
                ti: {component: props => Vue.h(props.tag, {class: ['ti', props.icon]})}
            },
            aliases: {
                collapse: 'ti-chevron-up', complete: 'ti-check', cancel: 'ti-circle-x',
                close: 'ti-x', delete: 'ti-circle-x', clear: 'ti-circle-x',
                success: 'ti-circle-check', info: 'ti-info-circle', warning: 'ti-alert-circle',
                error: 'ti-circle-x', prev: 'ti-chevron-left', next: 'ti-chevron-right',
                checkboxOn: 'ti-square-check', checkboxOff: 'ti-square',
                checkboxIndeterminate: 'ti-square-minus', delimiter: 'ti-point',
                sortAsc: 'ti-arrow-up', sortDesc: 'ti-arrow-down', expand: 'ti-chevron-down',
                menu: 'ti-menu-2', subgroup: 'ti-caret-down', dropdown: 'ti-caret-down',
                radioOn: 'ti-circle-dot', radioOff: 'ti-circle', edit: 'ti-pencil',
                ratingEmpty: 'ti-star', ratingFull: 'ti-star', ratingHalf: 'ti-star-half',
                loading: 'ti-refresh', first: 'ti-chevrons-left', last: 'ti-chevrons-right',
                unfold: 'ti-selector', file: 'ti-paperclip', plus: 'ti-plus', minus: 'ti-minus',
                calendar: 'ti-calendar', treeviewCollapse: 'ti-caret-down',
                treeviewExpand: 'ti-caret-right', tableGroupCollapse: 'ti-chevron-down',
                tableGroupExpand: 'ti-chevron-right', eyeDropper: 'ti-color-picker',
                upload: 'ti-cloud-upload', color: 'ti-palette', search: 'ti-search'
            }
        }
    }
};
