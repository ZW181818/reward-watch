import { useState } from 'react';
import { SymbolView } from 'expo-symbols';
import { Pressable, Text, View } from 'react-native';

import { languageOptions, useLanguage } from '@/lib/i18n';
import { createThemedStyles, themedForeground } from '@/lib/themed-styles';

export function LanguageSelector() {
  const { language, setLanguage, t } = useLanguage();
  const [isOpen, setIsOpen] = useState(false);
  const currentLanguage = languageOptions.find((option) => option.code === language) ?? languageOptions[0];

  return (
    <View style={styles.wrapper}>
      <Pressable
        accessibilityLabel={t('chooseLanguage')}
        accessibilityRole="button"
        onPress={() => setIsOpen((current) => !current)}
        style={[styles.button, isOpen && styles.buttonActive]}>
        <SymbolView
          name={{ ios: 'character.book.closed', android: 'translate', web: 'translate' }}
          size={17}
          tintColor={themedForeground('#5B4DFF')}
        />
        <Text style={styles.buttonText}>{currentLanguage.shortLabel}</Text>
        <SymbolView
          name={{ ios: isOpen ? 'chevron.up' : 'chevron.down', android: isOpen ? 'expand_less' : 'expand_more', web: isOpen ? 'expand_less' : 'expand_more' }}
          size={14}
          tintColor={themedForeground('#7B8497')}
        />
      </Pressable>

      {isOpen ? (
        <View style={styles.menu}>
          <Text style={styles.menuLabel}>{t('language')}</Text>
          {languageOptions.map((option) => {
            const isSelected = option.code === language;

            return (
              <Pressable
                accessibilityRole="button"
                key={option.code}
                onPress={() => {
                  setLanguage(option.code);
                  setIsOpen(false);
                }}
                style={[styles.menuItem, isSelected && styles.menuItemActive]}>
                <Text style={[styles.menuItemText, isSelected && styles.menuItemTextActive]}>
                  {option.label}
                </Text>
                {isSelected ? (
                  <SymbolView
                    name={{ ios: 'checkmark', android: 'check', web: 'check' }}
                    size={16}
                    tintColor={themedForeground('#5B4DFF')}
                  />
                ) : null}
              </Pressable>
            );
          })}
        </View>
      ) : null}
    </View>
  );
}

const styles = createThemedStyles({
  wrapper: {
    alignItems: 'flex-end',
    position: 'relative',
    zIndex: 40,
  },
  button: {
    alignItems: 'center',
    backgroundColor: 'rgba(255, 255, 255, 0.78)',
    borderColor: '#DDE4F2',
    borderRadius: 11,
    borderWidth: 1,
    flexDirection: 'row',
    gap: 7,
    minHeight: 42,
    paddingHorizontal: 12,
    boxShadow: '0 10px 24px rgba(81, 99, 143, 0.09)',
  },
  buttonActive: {
    borderColor: '#C7D2FE',
  },
  buttonText: {
    color: '#5B4DFF',
    fontSize: 14,
    fontWeight: '900',
  },
  menu: {
    backgroundColor: '#FFFFFF',
    borderColor: '#DDE4F2',
    borderRadius: 13,
    borderWidth: 1,
    gap: 3,
    minWidth: 176,
    padding: 6,
    position: 'absolute',
    right: 0,
    top: 50,
    zIndex: 50,
    boxShadow: '0 18px 36px rgba(50, 65, 100, 0.16)',
  },
  menuLabel: {
    color: '#98A2B3',
    fontSize: 11,
    fontWeight: '900',
    paddingHorizontal: 10,
    paddingBottom: 4,
    paddingTop: 6,
    textTransform: 'uppercase',
  },
  menuItem: {
    alignItems: 'center',
    borderRadius: 9,
    flexDirection: 'row',
    justifyContent: 'space-between',
    minHeight: 40,
    paddingHorizontal: 10,
  },
  menuItemActive: {
    backgroundColor: '#F3F4FF',
  },
  menuItemText: {
    color: '#475467',
    fontSize: 14,
    fontWeight: '800',
  },
  menuItemTextActive: {
    color: '#5B4DFF',
  },
});
