import { StyleSheet, Text, TextInput, type TextInputProps, View } from 'react-native';
import { colors } from '@/shared/theme/tokens';

type Props = TextInputProps & { label: string };

export function AuthField({ label, ...props }: Props) {
  return (
    <View style={styles.wrapper}>
      <Text style={styles.label}>{label}</Text>
      <TextInput
        accessibilityLabel={label}
        placeholderTextColor={colors.subtle}
        selectionColor={colors.accent}
        style={styles.input}
        {...props}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  wrapper: { gap: 8 },
  label: { color: colors.muted, fontSize: 14, lineHeight: 22 },
  input: {
    minHeight: 52,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 14,
    paddingHorizontal: 16,
    color: colors.text,
    backgroundColor: colors.surface,
    fontSize: 16,
  },
});
