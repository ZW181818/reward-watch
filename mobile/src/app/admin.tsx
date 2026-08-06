import { Image } from 'expo-image';
import { Link } from 'expo-router';
import { SymbolView } from 'expo-symbols';
import { useCallback, useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Switch,
  Text,
  TextInput,
  useWindowDimensions,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { AdminImagePicker, type AdminUploadFile } from '@/components/admin-image-picker';
import {
  changeAdminPassword,
  clearAdminToken,
  createAdminCase,
  deleteAdminManualCase,
  fetchAdminCase,
  fetchAdminCases,
  fetchAdminDashboard,
  fetchAdminHomeSettings,
  fetchAuditLog,
  loadAdminToken,
  loginAdmin,
  publishAdminHomeSettings,
  resetAdminCase,
  resolveAdminImage,
  saveAdminToken,
  saveAdminHomeSettings,
  triggerAdminSync,
  updateAdminCase,
  uploadAdminImage,
  type AdminCaseDetail,
  type AdminCaseSummary,
  type AdminDashboard,
  type AuditEntry,
  type HomeSettings,
  type ManualCaseInput,
} from '@/lib/admin-api';


type AdminView = 'overview' | 'cases' | 'settings' | 'audit';
type VisibilityFilter = 'all' | 'visible' | 'hidden';

function useDebouncedValue(value: string, delayMs: number) {
  const [nextValue, setNextValue] = useState(value);
  useEffect(() => {
    const timeout = setTimeout(() => setNextValue(value.trim()), delayMs);
    return () => clearTimeout(timeout);
  }, [delayMs, value]);
  return nextValue;
}

export default function AdminScreen() {
  const [token, setToken] = useState<string | null>(null);
  const [checkingToken, setCheckingToken] = useState(true);

  useEffect(() => {
    loadAdminToken().then(setToken).finally(() => setCheckingToken(false));
  }, []);

  if (checkingToken) {
    return <CenteredLoader label="Opening operations console" />;
  }
  if (!token) {
    return <AdminLogin onAuthenticated={setToken} />;
  }
  return <AdminWorkspace onSignOut={() => setToken(null)} token={token} />;
}

function AdminLogin({ onAuthenticated }: { onAuthenticated: (token: string) => void }) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    setIsSubmitting(true);
    try {
      const response = await loginAdmin(email.trim(), password);
      await saveAdminToken(response.accessToken);
      onAuthenticated(response.accessToken);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Unable to sign in');
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <SafeAreaView style={styles.loginPage}>
      <View style={styles.loginTopBar}>
        <Link href="/" asChild>
          <Pressable accessibilityRole="link" style={styles.backLink}>
            <SymbolView name={{ ios: 'arrow.left', android: 'arrow_back', web: 'arrow_back' }} size={17} tintColor="#5B4DFF" />
            <Text style={styles.backLinkText}>Reward Watch</Text>
          </Pressable>
        </Link>
      </View>
      <View style={styles.loginPanel}>
        <View style={styles.adminMark}>
          <SymbolView name={{ ios: 'lock.shield.fill', android: 'admin_panel_settings', web: 'admin_panel_settings' }} size={27} tintColor="#FFFFFF" />
        </View>
        <View style={styles.loginHeading}>
          <Text style={styles.loginTitle}>Operations Console</Text>
          <Text style={styles.loginSubtitle}>Reward Watch internal administration</Text>
        </View>
        <Field label="Email">
          <TextInput autoCapitalize="none" keyboardType="email-address" onChangeText={setEmail} style={styles.textInput} value={email} />
        </Field>
        <Field label="Password">
          <TextInput onChangeText={setPassword} onSubmitEditing={submit} secureTextEntry style={styles.textInput} value={password} />
        </Field>
        {error ? <Text style={styles.formError}>{error}</Text> : null}
        <Pressable disabled={isSubmitting || !email || !password} onPress={submit} style={[styles.primaryButton, (isSubmitting || !email || !password) && styles.buttonDisabled]}>
          {isSubmitting ? <ActivityIndicator color="#FFFFFF" /> : <Text style={styles.primaryButtonText}>Sign in</Text>}
        </Pressable>
      </View>
    </SafeAreaView>
  );
}

function AdminWorkspace({ onSignOut, token }: { onSignOut: () => void; token: string }) {
  const [view, setView] = useState<AdminView>('overview');
  const [dashboard, setDashboard] = useState<AdminDashboard | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const { width } = useWindowDimensions();
  const isWide = width >= 920;
  const usesIconOnlyNavigation = width < 680;

  const refreshDashboard = useCallback(async () => {
    try {
      setDashboard(await fetchAdminDashboard(token));
      setError(null);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Unable to load dashboard');
    } finally {
      setIsLoading(false);
    }
  }, [token]);

  useEffect(() => {
    refreshDashboard();
  }, [refreshDashboard]);

  async function signOut() {
    await clearAdminToken();
    onSignOut();
  }

  return (
    <SafeAreaView style={styles.adminPage}>
      <View style={[styles.workspace, !isWide && styles.workspaceCompact]}>
        <View style={[styles.sidebar, !isWide && styles.sidebarCompact]}>
          <View style={styles.sidebarBrand}>
            <View style={styles.sidebarMark}>
              <SymbolView name={{ ios: 'checkmark.shield.fill', android: 'verified_user', web: 'verified_user' }} size={20} tintColor="#FFFFFF" />
            </View>
            <View style={styles.sidebarBrandCopy}>
              <Text style={styles.sidebarTitle}>Reward Watch</Text>
              <Text style={styles.sidebarMeta}>Operations</Text>
            </View>
          </View>
          <View style={[styles.nav, !isWide && styles.navCompact]}>
            <NavButton active={view === 'overview'} icon="dashboard" iconOnly={usesIconOnlyNavigation} label="Overview" onPress={() => setView('overview')} />
            <NavButton active={view === 'cases'} icon="folder" iconOnly={usesIconOnlyNavigation} label="Cases" onPress={() => setView('cases')} />
            <NavButton active={view === 'settings'} icon="settings" iconOnly={usesIconOnlyNavigation} label="Home" onPress={() => setView('settings')} />
            <NavButton active={view === 'audit'} icon="history" iconOnly={usesIconOnlyNavigation} label="Audit" onPress={() => setView('audit')} />
          </View>
          {isWide ? (
            <View style={styles.sidebarFooter}>
              <Text style={styles.adminEmail} numberOfLines={1}>{dashboard?.adminEmail}</Text>
              <Pressable onPress={signOut} style={styles.signOutButton}>
                <SymbolView name={{ ios: 'rectangle.portrait.and.arrow.right', android: 'logout', web: 'logout' }} size={17} tintColor="#667085" />
                <Text style={styles.signOutText}>Sign out</Text>
              </Pressable>
            </View>
          ) : null}
        </View>

        <ScrollView contentContainerStyle={styles.adminContent} showsVerticalScrollIndicator={false}>
          <View style={styles.contentHeader}>
            <View>
              <Text style={styles.contentEyebrow}>INTERNAL OPERATIONS</Text>
              <Text style={styles.contentTitle}>{view === 'overview' ? 'Overview' : view === 'cases' ? 'Case Management' : view === 'settings' ? 'Home Publishing' : 'Audit Log'}</Text>
            </View>
            {!isWide ? <Pressable onPress={signOut} style={styles.iconButton}><SymbolView name={{ ios: 'rectangle.portrait.and.arrow.right', android: 'logout', web: 'logout' }} size={19} tintColor="#475467" /></Pressable> : null}
          </View>
          {error ? <Notice text={error} /> : null}
          {isLoading ? <CenteredLoader label="Loading operations data" embedded /> : view === 'overview' ? (
            <Overview dashboard={dashboard} onRefresh={refreshDashboard} token={token} />
          ) : view === 'cases' ? (
            <CasesManager token={token} />
          ) : view === 'settings' ? (
            <SettingsPanel token={token} />
          ) : (
            <AuditPanel token={token} />
          )}
        </ScrollView>
      </View>
    </SafeAreaView>
  );
}

function NavButton({ active, icon, iconOnly, label, onPress }: { active: boolean; icon: 'dashboard' | 'folder' | 'settings' | 'history'; iconOnly: boolean; label: string; onPress: () => void }) {
  const names = icon === 'dashboard'
    ? { ios: 'rectangle.3.group.fill' as const, android: 'dashboard' as const, web: 'dashboard' as const }
    : icon === 'folder'
      ? { ios: 'folder.fill' as const, android: 'folder' as const, web: 'folder' as const }
      : icon === 'settings'
        ? { ios: 'house.and.flag.fill' as const, android: 'home_work' as const, web: 'home_work' as const }
        : { ios: 'clock.arrow.circlepath' as const, android: 'history' as const, web: 'history' as const };
  return (
    <Pressable accessibilityLabel={label} onPress={onPress} style={[styles.navButton, iconOnly && styles.navButtonIconOnly, active && styles.navButtonActive]}>
      <SymbolView name={names} size={19} tintColor={active ? '#5B4DFF' : '#667085'} />
      {iconOnly ? null : <Text style={[styles.navButtonText, active && styles.navButtonTextActive]}>{label}</Text>}
    </Pressable>
  );
}

function Overview({ dashboard, onRefresh, token }: { dashboard: AdminDashboard | null; onRefresh: () => Promise<void>; token: string }) {
  const [syncing, setSyncing] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  async function runSync() {
    setSyncing(true);
    try {
      await triggerAdminSync(token);
      setMessage('Sync accepted');
      await onRefresh();
    } catch (requestError) {
      setMessage(requestError instanceof Error ? requestError.message : 'Unable to start sync');
    } finally {
      setSyncing(false);
    }
  }

  const updatedAt = dashboard?.sync?.updatedAt
    ? new Date(dashboard.sync.updatedAt).toLocaleString()
    : 'No completed sync';

  return (
    <View style={styles.sectionStack}>
      <View style={styles.metricsGrid}>
        <AdminMetric label="Canonical cases" value={dashboard?.counts.cases ?? 0} tone="neutral" />
        <AdminMetric label="Hidden" value={dashboard?.counts.hidden ?? 0} tone="warning" />
        <AdminMetric label="Draft changes" value={dashboard?.counts.drafts ?? 0} tone="blue" />
        <AdminMetric label="Official sources" value={dashboard?.sync?.sources.length ?? 0} tone="green" />
      </View>

      <View style={styles.panel}>
        <View style={styles.panelHeader}>
          <View style={styles.panelHeadingCopy}>
            <Text style={styles.panelTitle}>Data pipeline</Text>
            <Text style={styles.panelMeta}>Last completed {updatedAt}</Text>
          </View>
          <Pressable disabled={syncing || dashboard?.syncRunning} onPress={runSync} style={[styles.secondaryButton, (syncing || dashboard?.syncRunning) && styles.buttonDisabled]}>
            <SymbolView name={{ ios: 'arrow.clockwise', android: 'sync', web: 'sync' }} size={17} tintColor="#5B4DFF" />
            <Text style={styles.secondaryButtonText}>{dashboard?.syncRunning ? 'Running' : 'Run sync'}</Text>
          </Pressable>
        </View>
        {message ? <Text style={styles.inlineMessage}>{message}</Text> : null}
        <View style={styles.sourceTable}>
          {dashboard?.sync?.sources.map((source) => (
            <View key={source.id} style={styles.sourceRow}>
              <View style={[styles.healthDot, source.success ? styles.healthGood : styles.healthBad]} />
              <View style={styles.sourceRowCopy}>
                <Text style={styles.sourceRowName} numberOfLines={1}>{source.name}</Text>
                <Text style={styles.sourceRowMeta}>{source.country} · {source.count.toLocaleString()} cases</Text>
              </View>
              <Text style={[styles.sourceState, source.success ? styles.sourceStateGood : styles.sourceStateBad]}>{source.success ? 'Fresh' : 'Stale'}</Text>
            </View>
          ))}
        </View>
      </View>

      <PasswordPanel token={token} />
    </View>
  );
}

function AdminMetric({ label, tone, value }: { label: string; tone: 'neutral' | 'warning' | 'blue' | 'green'; value: number }) {
  const toneStyle = tone === 'warning' ? styles.metricWarning : tone === 'blue' ? styles.metricBlue : tone === 'green' ? styles.metricGreen : styles.metricNeutral;
  return (
    <View style={styles.adminMetric}>
      <View style={[styles.metricMarker, toneStyle]} />
      <Text style={styles.adminMetricValue}>{value.toLocaleString()}</Text>
      <Text style={styles.adminMetricLabel}>{label}</Text>
    </View>
  );
}

function PasswordPanel({ token }: { token: string }) {
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmation, setConfirmation] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const canSave = Boolean(
    currentPassword && newPassword.length >= 12 && newPassword === confirmation
  );

  async function submit() {
    if (!canSave) return;
    setIsSaving(true);
    setMessage(null);
    try {
      await changeAdminPassword(token, currentPassword, newPassword);
      setCurrentPassword('');
      setNewPassword('');
      setConfirmation('');
      setMessage('Password updated. Your current session remains active.');
    } catch (requestError) {
      setMessage(requestError instanceof Error ? requestError.message : 'Unable to update password');
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <View style={styles.panel}>
      <View style={styles.panelHeader}>
        <View style={styles.panelHeadingCopy}>
          <Text style={styles.panelTitle}>Account security</Text>
          <Text style={styles.panelMeta}>Use at least 12 characters. Passwords are never shown in the audit log.</Text>
        </View>
      </View>
      <View style={styles.securityForm}>
        <Field label="Current password">
          <TextInput
            autoCapitalize="none"
            onChangeText={setCurrentPassword}
            onSubmitEditing={submit}
            secureTextEntry
            style={styles.textInput}
            value={currentPassword}
          />
        </Field>
        <Field label="New password">
          <TextInput
            autoCapitalize="none"
            onChangeText={setNewPassword}
            onSubmitEditing={submit}
            secureTextEntry
            style={styles.textInput}
            value={newPassword}
          />
        </Field>
        <Field label="Confirm new password">
          <TextInput
            autoCapitalize="none"
            onChangeText={setConfirmation}
            onSubmitEditing={submit}
            secureTextEntry
            style={styles.textInput}
            value={confirmation}
          />
        </Field>
        {confirmation && confirmation !== newPassword ? (
          <Text style={styles.securityError}>The new passwords do not match.</Text>
        ) : null}
        {message ? <Text style={styles.securityMessage}>{message}</Text> : null}
        <Pressable
          disabled={!canSave || isSaving}
          onPress={submit}
          style={[styles.primaryButton, styles.securityButton, (!canSave || isSaving) && styles.buttonDisabled]}>
          {isSaving ? <ActivityIndicator color="#FFFFFF" /> : <Text style={styles.primaryButtonText}>Update password</Text>}
        </Pressable>
      </View>
    </View>
  );
}

function CasesManager({ token }: { token: string }) {
  const [query, setQuery] = useState('');
  const [visibility, setVisibility] = useState<VisibilityFilter>('all');
  const [cases, setCases] = useState<AdminCaseSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<AdminCaseDetail | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const debouncedQuery = useDebouncedValue(query, 300);
  const totalPages = Math.max(1, Math.ceil(total / 20));
  const { width } = useWindowDimensions();
  const hasSplitEditor = width >= 1080;

  const loadCases = useCallback(async (nextPage: number) => {
    setIsLoading(true);
    try {
      const response = await fetchAdminCases(token, {
        page: nextPage,
        q: debouncedQuery || undefined,
        visibility,
      });
      setCases(response.items);
      setTotal(response.total);
      setPage(response.page);
      setError(null);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Unable to load cases');
    } finally {
      setIsLoading(false);
    }
  }, [debouncedQuery, token, visibility]);

  useEffect(() => {
    loadCases(1);
  }, [loadCases]);

  async function openCase(caseId: string) {
    setIsCreating(false);
    setSelectedId(caseId);
    setDetail(null);
    try {
      setDetail(await fetchAdminCase(token, caseId));
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Unable to open case');
    }
  }

  return (
    <View style={styles.caseManager}>
      <View style={styles.caseToolbar}>
        <View style={styles.adminSearch}>
          <SymbolView name={{ ios: 'magnifyingglass', android: 'search', web: 'search' }} size={20} tintColor="#667085" />
          <TextInput autoCapitalize="none" onChangeText={setQuery} placeholder="Search case ID, title or source" placeholderTextColor="#98A2B3" style={styles.adminSearchInput} value={query} />
        </View>
        <View style={styles.smallSegment}>
          {(['all', 'visible', 'hidden'] as VisibilityFilter[]).map((item) => (
            <Pressable key={item} onPress={() => setVisibility(item)} style={[styles.smallSegmentButton, visibility === item && styles.smallSegmentButtonActive]}>
              <Text style={[styles.smallSegmentText, visibility === item && styles.smallSegmentTextActive]}>{item[0].toUpperCase() + item.slice(1)}</Text>
            </Pressable>
          ))}
        </View>
        <Pressable
          onPress={() => {
            setSelectedId(null);
            setDetail(null);
            setIsCreating(true);
          }}
          style={styles.createButton}>
          <SymbolView name={{ ios: 'plus', android: 'add', web: 'add' }} size={17} tintColor="#FFFFFF" />
          <Text style={styles.createButtonText}>New notice</Text>
        </Pressable>
      </View>
      {error ? <Notice text={error} /> : null}

      <View style={[styles.caseWorkspace, !hasSplitEditor && styles.caseWorkspaceCompact]}>
        <View style={[styles.caseListPanel, !hasSplitEditor && styles.caseListPanelCompact]}>
          <View style={styles.listCountRow}>
            <Text style={styles.listCount}>{total.toLocaleString()} cases</Text>
            <Text style={styles.panelMeta}>Page {page} of {totalPages}</Text>
          </View>
          {isLoading ? <CenteredLoader embedded label="Loading cases" /> : (
            <View style={styles.adminCaseList}>
              {cases.map((rewardCase) => (
                <Pressable key={rewardCase.id} onPress={() => openCase(rewardCase.id)} style={[styles.adminCaseRow, selectedId === rewardCase.id && styles.adminCaseRowSelected]}>
                  {rewardCase.imageUrl ? <Image contentFit="cover" source={resolveAdminImage(rewardCase.imageUrl)} style={styles.adminCaseImage} /> : <View style={styles.adminCaseImageFallback}><SymbolView name={{ ios: 'photo', android: 'image', web: 'image' }} size={19} tintColor="#98A2B3" /></View>}
                  <View style={styles.adminCaseCopy}>
                    <Text style={styles.adminCaseTitle} numberOfLines={1}>{rewardCase.title}</Text>
                    <Text style={styles.adminCaseMeta} numberOfLines={1}>{rewardCase.sourceName} · {rewardCase.country}</Text>
                    <View style={styles.adminCaseFlags}>
                      <Text style={[styles.miniStatus, !rewardCase.isVisible && styles.miniStatusHidden]}>{rewardCase.isVisible ? rewardCase.status : 'Hidden'}</Text>
                      {rewardCase.hasOverride ? <Text style={styles.overrideLabel}>Edited</Text> : null}
                      {rewardCase.isManual ? <Text style={styles.manualLabel}>Manual</Text> : null}
                    </View>
                  </View>
                  <SymbolView name={{ ios: 'chevron.right', android: 'chevron_right', web: 'chevron_right' }} size={17} tintColor="#98A2B3" />
                </Pressable>
              ))}
            </View>
          )}
          <View style={styles.pagination}>
            <Pressable disabled={page <= 1} onPress={() => loadCases(page - 1)} style={[styles.pageButton, page <= 1 && styles.buttonDisabled]}><SymbolView name={{ ios: 'chevron.left', android: 'chevron_left', web: 'chevron_left' }} size={17} tintColor="#475467" /></Pressable>
            <Pressable disabled={page >= totalPages} onPress={() => loadCases(page + 1)} style={[styles.pageButton, page >= totalPages && styles.buttonDisabled]}><SymbolView name={{ ios: 'chevron.right', android: 'chevron_right', web: 'chevron_right' }} size={17} tintColor="#475467" /></Pressable>
          </View>
        </View>

        <View style={[styles.editorPanel, !hasSplitEditor && styles.editorPanelCompact]}>
          {isCreating ? (
            <ManualCaseForm
              onCancel={() => setIsCreating(false)}
              onCreated={async (caseId) => {
                await loadCases(1);
                await openCase(caseId);
              }}
              token={token}
            />
          ) : selectedId && !detail ? <CenteredLoader embedded label="Opening case" /> : detail ? (
            <CaseEditor
              detail={detail}
              key={detail.effective.id}
              onChanged={async () => { await loadCases(page); await openCase(detail.effective.id); }}
              onDeleted={async () => {
                setSelectedId(null);
                setDetail(null);
                await loadCases(1);
              }}
              token={token}
            />
          ) : (
            <View style={styles.editorEmpty}>
              <SymbolView name={{ ios: 'slider.horizontal.3', android: 'tune', web: 'tune' }} size={28} tintColor="#98A2B3" />
              <Text style={styles.editorEmptyTitle}>Select a case</Text>
            </View>
          )}
        </View>
      </View>
    </View>
  );
}

async function uploadFiles(token: string, files: AdminUploadFile[]) {
  const uploadedUrls: string[] = [];
  for (const file of files) {
    const response = await uploadAdminImage(token, file.blob, file.name);
    uploadedUrls.push(response.url);
  }
  return uploadedUrls;
}

function ManualCaseForm({
  onCancel,
  onCreated,
  token,
}: {
  onCancel: () => void;
  onCreated: (caseId: string) => Promise<void>;
  token: string;
}) {
  const [title, setTitle] = useState('');
  const [summary, setSummary] = useState('');
  const [country, setCountry] = useState<'US' | 'Canada'>('US');
  const [regions, setRegions] = useState('');
  const [generalLocation, setGeneralLocation] = useState('');
  const [caseType, setCaseType] = useState('Public reward notice');
  const [status, setStatus] = useState<ManualCaseInput['status']>('Information Requested');
  const [reward, setReward] = useState('');
  const [currency, setCurrency] = useState<'USD' | 'CAD'>('USD');
  const [publishedDate, setPublishedDate] = useState(new Date().toISOString().slice(0, 10));
  const [sourceAuthor, setSourceAuthor] = useState('');
  const [sourceTitle, setSourceTitle] = useState('');
  const [sourceUrl, setSourceUrl] = useState('');
  const [note, setNote] = useState('');
  const [imageUrls, setImageUrls] = useState<string[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const regionList = regions.split(',').map((value) => value.trim()).filter(Boolean);
  const canSave = Boolean(
    title.trim().length >= 4 &&
    summary.trim().length >= 20 &&
    regionList.length &&
    sourceAuthor.trim() &&
    sourceTitle.trim() &&
    /^https?:\/\//i.test(sourceUrl.trim()) &&
    publishedDate
  );

  async function handleFiles(files: AdminUploadFile[]) {
    if (!files.length) return;
    if (imageUrls.length + files.length > 8) {
      setMessage('A notice can contain up to 8 photos.');
      return;
    }
    setIsUploading(true);
    setMessage(null);
    try {
      const uploaded = await uploadFiles(token, files);
      setImageUrls((current) => [...current, ...uploaded]);
    } catch (requestError) {
      setMessage(requestError instanceof Error ? requestError.message : 'Unable to upload photos');
    } finally {
      setIsUploading(false);
    }
  }

  async function saveDraft() {
    setIsSaving(true);
    setMessage(null);
    try {
      const response = await createAdminCase(token, {
        title: title.trim(),
        summary: summary.trim(),
        country,
        regions: regionList,
        generalLocation: generalLocation.trim() || null,
        caseType: caseType.trim() || null,
        status,
        reward: reward.trim() ? Number(reward.replace(/,/g, '')) : null,
        rewardCurrency: reward.trim() ? currency : null,
        publishedDate,
        sourceUrl: sourceUrl.trim(),
        sourceTitle: sourceTitle.trim(),
        sourceAuthor: sourceAuthor.trim(),
        imageUrls,
        note: note.trim() || null,
      });
      await onCreated(response.case.id);
    } catch (requestError) {
      setMessage(requestError instanceof Error ? requestError.message : 'Unable to create notice');
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <ScrollView contentContainerStyle={styles.editorContent} nestedScrollEnabled>
      <View style={styles.editorHeader}>
        <View style={styles.editorHeaderCopy}>
          <Text style={styles.editorId}>New verified notice</Text>
          <Text style={styles.editorSource}>Saved as a hidden draft until you publish it</Text>
        </View>
        <Text style={styles.draftBadge}>Draft</Text>
      </View>

      <View style={styles.editorNotice}>
        <SymbolView name={{ ios: 'checkmark.shield', android: 'verified_user', web: 'verified_user' }} size={19} tintColor="#475467" />
        <Text style={styles.editorNoticeText}>
          A public source URL and publishing organization are required. Enter only a general jurisdiction or city area, never a live location, home address, or movement history.
        </Text>
      </View>

      <Field label="Display title"><TextInput onChangeText={setTitle} placeholder="Public notice title" placeholderTextColor="#98A2B3" style={styles.textInput} value={title} /></Field>
      <Field label="Summary"><TextInput multiline onChangeText={setSummary} placeholder="Factual summary from the published source" placeholderTextColor="#98A2B3" style={[styles.textInput, styles.textArea]} textAlignVertical="top" value={summary} /></Field>

      <View style={styles.editorTwoColumns}>
        <Field grow label="Country">
          <View style={styles.smallSegment}>{(['US', 'Canada'] as const).map((value) => <Pressable key={value} onPress={() => { setCountry(value); setCurrency(value === 'Canada' ? 'CAD' : 'USD'); }} style={[styles.smallSegmentButton, country === value && styles.smallSegmentButtonActive]}><Text style={[styles.smallSegmentText, country === value && styles.smallSegmentTextActive]}>{value}</Text></Pressable>)}</View>
        </Field>
        <Field grow label="State / province"><TextInput onChangeText={setRegions} placeholder="Washington, Oregon" placeholderTextColor="#98A2B3" style={styles.textInput} value={regions} /></Field>
      </View>
      <Field label="General area (optional)"><TextInput onChangeText={setGeneralLocation} placeholder="City or broad jurisdiction only" placeholderTextColor="#98A2B3" style={styles.textInput} value={generalLocation} /></Field>

      <View style={styles.editorTwoColumns}>
        <Field grow label="Notice type"><TextInput onChangeText={setCaseType} style={styles.textInput} value={caseType} /></Field>
        <Field grow label="Published date"><TextInput onChangeText={setPublishedDate} placeholder="YYYY-MM-DD" placeholderTextColor="#98A2B3" style={styles.textInput} value={publishedDate} /></Field>
      </View>

      <Field label="Status">
        <View style={styles.chipRow}>{(['Information Requested', 'Open', 'Closed'] as const).map((value) => <Pressable key={value} onPress={() => setStatus(value)} style={[styles.statusChoice, status === value && styles.statusChoiceActive]}><Text style={[styles.statusChoiceText, status === value && styles.statusChoiceTextActive]}>{value}</Text></Pressable>)}</View>
      </Field>
      <View style={styles.editorTwoColumns}>
        <Field grow label="Reward amount"><TextInput keyboardType="numeric" onChangeText={setReward} placeholder="Leave blank if not published" placeholderTextColor="#98A2B3" style={styles.textInput} value={reward} /></Field>
        <Field grow label="Currency"><View style={styles.smallSegment}>{(['USD', 'CAD'] as const).map((value) => <Pressable key={value} onPress={() => setCurrency(value)} style={[styles.smallSegmentButton, currency === value && styles.smallSegmentButtonActive]}><Text style={[styles.smallSegmentText, currency === value && styles.smallSegmentTextActive]}>{value}</Text></Pressable>)}</View></Field>
      </View>

      <View style={styles.formDivider} />
      <Text style={styles.formSectionTitle}>Source verification</Text>
      <Field label="Publishing organization"><TextInput onChangeText={setSourceAuthor} placeholder="Organization shown on the source page" placeholderTextColor="#98A2B3" style={styles.textInput} value={sourceAuthor} /></Field>
      <Field label="Source page title"><TextInput onChangeText={setSourceTitle} placeholder="Exact title of the public notice" placeholderTextColor="#98A2B3" style={styles.textInput} value={sourceTitle} /></Field>
      <Field label="Public source URL"><TextInput autoCapitalize="none" keyboardType="url" onChangeText={setSourceUrl} placeholder="https://..." placeholderTextColor="#98A2B3" style={styles.textInput} value={sourceUrl} /></Field>

      <View style={styles.formDivider} />
      <Text style={styles.formSectionTitle}>Photos</Text>
      <Text style={styles.fieldHint}>JPEG, PNG, or WebP. Up to 8 files, 10 MB each. Metadata is removed during upload.</Text>
      {imageUrls.length ? (
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.galleryRow}>
          {imageUrls.map((url, index) => (
            <View key={url} style={styles.uploadedImageWrap}>
              <Image contentFit="cover" source={resolveAdminImage(url)} style={styles.galleryImage} />
              <Pressable accessibilityLabel={`Remove photo ${index + 1}`} onPress={() => setImageUrls((current) => current.filter((item) => item !== url))} style={styles.removePhotoButton}>
                <SymbolView name={{ ios: 'xmark', android: 'close', web: 'close' }} size={14} tintColor="#FFFFFF" />
              </Pressable>
            </View>
          ))}
        </ScrollView>
      ) : null}
      <AdminImagePicker disabled={isUploading || imageUrls.length >= 8} onFiles={handleFiles} />

      <Field label="Internal review note (optional)"><TextInput multiline onChangeText={setNote} style={[styles.textInput, styles.noteArea]} textAlignVertical="top" value={note} /></Field>
      {message ? <Text style={styles.inlineMessage}>{message}</Text> : null}
      <View style={styles.editorActions}>
        <Pressable disabled={isSaving} onPress={onCancel} style={styles.tertiaryButton}><Text style={styles.tertiaryButtonText}>Cancel</Text></Pressable>
        <Pressable disabled={isSaving || isUploading || !canSave} onPress={saveDraft} style={[styles.primaryButton, (isSaving || isUploading || !canSave) && styles.buttonDisabled]}>{isSaving ? <ActivityIndicator color="#FFFFFF" /> : <Text style={styles.primaryButtonText}>Save draft</Text>}</Pressable>
      </View>
    </ScrollView>
  );
}

function CaseEditor({ detail, onChanged, onDeleted, token }: { detail: AdminCaseDetail; onChanged: () => Promise<void>; onDeleted: () => Promise<void>; token: string }) {
  const rewardCase = detail.effective;
  const [title, setTitle] = useState(rewardCase.title);
  const [summary, setSummary] = useState(rewardCase.summary);
  const [status, setStatus] = useState(rewardCase.status);
  const [reward, setReward] = useState(rewardCase.reward?.toString() ?? '');
  const [currency, setCurrency] = useState(rewardCase.rewardCurrency ?? 'USD');
  const [regions, setRegions] = useState((rewardCase.regions ?? []).join(', '));
  const [generalLocation, setGeneralLocation] = useState(rewardCase.locations ?? '');
  const [caseType, setCaseType] = useState(rewardCase.caseType ?? '');
  const [publishedDate, setPublishedDate] = useState(rewardCase.publishedDate);
  const [sourceAuthor, setSourceAuthor] = useState(rewardCase.sourceAuthor ?? rewardCase.agency);
  const [sourceTitle, setSourceTitle] = useState(rewardCase.sourceTitle ?? '');
  const [sourceUrl, setSourceUrl] = useState(rewardCase.sourceUrl);
  const [imageUrl, setImageUrl] = useState(rewardCase.imageUrl ?? '');
  const [imageUrls, setImageUrls] = useState(rewardCase.imageUrls ?? []);
  const [isVisible, setIsVisible] = useState(detail.override?.isVisible ?? true);
  const [reviewStatus, setReviewStatus] = useState<'draft' | 'published'>(detail.override?.reviewStatus ?? 'published');
  const [note, setNote] = useState(detail.override?.note ?? '');
  const [isSaving, setIsSaving] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  async function handleFiles(files: AdminUploadFile[]) {
    if (!files.length) return;
    if (imageUrls.length + files.length > 8) {
      setMessage('A case can contain up to 8 photos.');
      return;
    }
    setIsUploading(true);
    try {
      const uploaded = await uploadFiles(token, files);
      setImageUrls((current) => [...current, ...uploaded]);
      setImageUrl((current) => current || uploaded[0] || '');
      setMessage('Photos uploaded. Save changes to publish them.');
    } catch (requestError) {
      setMessage(requestError instanceof Error ? requestError.message : 'Unable to upload photos');
    } finally {
      setIsUploading(false);
    }
  }

  async function save() {
    setIsSaving(true);
    try {
      await updateAdminCase(token, rewardCase.id, {
        title: title.trim(),
        summary: summary.trim(),
        status: status.trim(),
        reward: reward.trim() ? Number(reward.replace(/,/g, '')) : null,
        rewardCurrency: reward.trim() ? currency : null,
        imageUrl: imageUrl || null,
        imageUrls,
        ...(detail.isManual ? {
          regions: regions.split(',').map((value) => value.trim()).filter(Boolean),
          locations: generalLocation.trim() || null,
          caseType: caseType.trim() || null,
          publishedDate,
          sourceAuthor: sourceAuthor.trim(),
          sourceTitle: sourceTitle.trim(),
          sourceUrl: sourceUrl.trim(),
        } : {}),
        isVisible,
        reviewStatus,
        note: note.trim() || null,
      });
      setMessage('Saved');
      await onChanged();
    } catch (requestError) {
      setMessage(requestError instanceof Error ? requestError.message : 'Unable to save case');
    } finally {
      setIsSaving(false);
    }
  }

  async function reset() {
    setIsSaving(true);
    try {
      await resetAdminCase(token, rewardCase.id);
      setMessage('Official values restored');
      await onChanged();
    } catch (requestError) {
      setMessage(requestError instanceof Error ? requestError.message : 'Unable to reset case');
    } finally {
      setIsSaving(false);
    }
  }

  async function removeManualCase() {
    if (!confirmDelete) {
      setConfirmDelete(true);
      setMessage('Select Delete manual case again to confirm permanent removal.');
      return;
    }
    setIsSaving(true);
    try {
      await deleteAdminManualCase(token, rewardCase.id);
      await onDeleted();
    } catch (requestError) {
      setMessage(requestError instanceof Error ? requestError.message : 'Unable to delete case');
      setIsSaving(false);
    }
  }

  return (
    <ScrollView contentContainerStyle={styles.editorContent} nestedScrollEnabled>
      <View style={styles.editorHeader}>
        <View style={styles.editorHeaderCopy}>
          <Text style={styles.editorId}>{rewardCase.id}</Text>
          <Text style={styles.editorSource} numberOfLines={1}>{rewardCase.sourceAuthor ?? rewardCase.agency}</Text>
        </View>
        {detail.override ? <Text style={styles.overrideBadge}>Override active</Text> : null}
      </View>

      <View style={styles.publishRow}>
        <View style={styles.publishCopy}><Text style={styles.fieldLabel}>Visible in app</Text><Text style={styles.fieldHint}>{isVisible ? 'Published' : 'Hidden'}</Text></View>
        <Switch onValueChange={setIsVisible} trackColor={{ false: '#D0D5DD', true: '#B8B3FF' }} thumbColor={isVisible ? '#5B4DFF' : '#FFFFFF'} value={isVisible} />
      </View>

      <Field label="Review status">
        <View style={styles.smallSegment}>
          {(['published', 'draft'] as const).map((value) => <Pressable key={value} onPress={() => setReviewStatus(value)} style={[styles.smallSegmentButton, reviewStatus === value && styles.smallSegmentButtonActive]}><Text style={[styles.smallSegmentText, reviewStatus === value && styles.smallSegmentTextActive]}>{value === 'published' ? 'Published' : 'Draft'}</Text></Pressable>)}
        </View>
      </Field>
      <Field label="Display title"><TextInput onChangeText={setTitle} style={styles.textInput} value={title} /></Field>
      <Field label="Summary"><TextInput multiline onChangeText={setSummary} style={[styles.textInput, styles.textArea]} textAlignVertical="top" value={summary} /></Field>
      {detail.isManual ? (
        <>
          <View style={styles.editorTwoColumns}>
            <Field grow label="State / province"><TextInput onChangeText={setRegions} style={styles.textInput} value={regions} /></Field>
            <Field grow label="General area"><TextInput onChangeText={setGeneralLocation} style={styles.textInput} value={generalLocation} /></Field>
          </View>
          <View style={styles.editorTwoColumns}>
            <Field grow label="Notice type"><TextInput onChangeText={setCaseType} style={styles.textInput} value={caseType} /></Field>
            <Field grow label="Published date"><TextInput onChangeText={setPublishedDate} style={styles.textInput} value={publishedDate} /></Field>
          </View>
          <Field label="Publishing organization"><TextInput onChangeText={setSourceAuthor} style={styles.textInput} value={sourceAuthor} /></Field>
          <Field label="Source page title"><TextInput onChangeText={setSourceTitle} style={styles.textInput} value={sourceTitle} /></Field>
          <Field label="Public source URL"><TextInput autoCapitalize="none" keyboardType="url" onChangeText={setSourceUrl} style={styles.textInput} value={sourceUrl} /></Field>
        </>
      ) : null}
      <View style={styles.editorTwoColumns}>
        <Field grow label="Status"><TextInput onChangeText={setStatus} style={styles.textInput} value={status} /></Field>
        <Field grow label="Reward"><TextInput keyboardType="numeric" onChangeText={setReward} placeholder="Not published" placeholderTextColor="#98A2B3" style={styles.textInput} value={reward} /></Field>
      </View>
      <Field label="Currency">
        <View style={styles.smallSegment}>{(['USD', 'CAD'] as const).map((value) => <Pressable key={value} onPress={() => setCurrency(value)} style={[styles.smallSegmentButton, currency === value && styles.smallSegmentButtonActive]}><Text style={[styles.smallSegmentText, currency === value && styles.smallSegmentTextActive]}>{value}</Text></Pressable>)}</View>
      </Field>

      <Field label="Case photos">
        {imageUrls.length ? <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.galleryRow}>{imageUrls.map((url) => <Pressable key={url} onPress={() => setImageUrl(url)} style={[styles.galleryChoice, imageUrl === url && styles.galleryChoiceSelected]}><Image contentFit="cover" source={resolveAdminImage(url)} style={styles.galleryImage} /></Pressable>)}</ScrollView> : null}
        <AdminImagePicker disabled={isUploading || imageUrls.length >= 8} onFiles={handleFiles} />
        <Text style={styles.fieldHint}>Select a thumbnail to use it as the cover image.</Text>
      </Field>
      <Field label="Internal note"><TextInput multiline onChangeText={setNote} style={[styles.textInput, styles.noteArea]} textAlignVertical="top" value={note} /></Field>
      {message ? <Text style={styles.inlineMessage}>{message}</Text> : null}
      <View style={styles.editorActions}>
        {detail.isManual ? (
          <Pressable disabled={isSaving} onPress={removeManualCase} style={[styles.deleteButton, confirmDelete && styles.deleteButtonConfirm]}><Text style={[styles.deleteButtonText, confirmDelete && styles.deleteButtonTextConfirm]}>Delete manual case</Text></Pressable>
        ) : (
          <Pressable disabled={isSaving} onPress={reset} style={styles.tertiaryButton}><Text style={styles.tertiaryButtonText}>Reset override</Text></Pressable>
        )}
        <Pressable disabled={isSaving || isUploading || !title.trim() || !summary.trim()} onPress={save} style={[styles.primaryButton, (isSaving || isUploading || !title.trim() || !summary.trim()) && styles.buttonDisabled]}>{isSaving ? <ActivityIndicator color="#FFFFFF" /> : <Text style={styles.primaryButtonText}>Save changes</Text>}</Pressable>
      </View>
    </ScrollView>
  );
}

function SettingsPanel({ token }: { token: string }) {
  const [published, setPublished] = useState<HomeSettings | null>(null);
  const [subtitle, setSubtitle] = useState('');
  const [safetyMessage, setSafetyMessage] = useState('');
  const [featuredIds, setFeaturedIds] = useState('');
  const [recentLimit, setRecentLimit] = useState(4);
  const [hasDraft, setHasDraft] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const load = useCallback(async () => {
    const response = await fetchAdminHomeSettings(token);
    const editable = response.draft ?? response.published;
    setPublished(response.published);
    setSubtitle(editable.brandSubtitle);
    setSafetyMessage(editable.safetyMessage);
    setFeaturedIds(editable.featuredCaseIds.join(', '));
    setRecentLimit(editable.recentCaseLimit);
    setHasDraft(response.draft !== null);
  }, [token]);

  useEffect(() => {
    load().catch((requestError: Error) => setMessage(requestError.message));
  }, [load]);

  function draftValue(): HomeSettings {
    return {
      brandSubtitle: subtitle.trim(),
      safetyMessage: safetyMessage.trim(),
      featuredCaseIds: featuredIds.split(',').map((value) => value.trim()).filter(Boolean),
      recentCaseLimit: recentLimit,
    };
  }

  async function saveDraft() {
    setIsSaving(true);
    try {
      await saveAdminHomeSettings(token, draftValue());
      setHasDraft(true);
      setMessage('Draft saved');
    } catch (requestError) {
      setMessage(requestError instanceof Error ? requestError.message : 'Unable to save draft');
    } finally {
      setIsSaving(false);
    }
  }

  async function publish() {
    setIsSaving(true);
    try {
      await publishAdminHomeSettings(token);
      await load();
      setMessage('Published to the app');
    } catch (requestError) {
      setMessage(requestError instanceof Error ? requestError.message : 'Unable to publish');
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <View style={styles.settingsLayout}>
      <View style={[styles.panel, styles.settingsPanel]}>
        <View style={styles.panelHeader}>
          <View style={styles.panelHeadingCopy}>
            <Text style={styles.panelTitle}>Home draft</Text>
            <Text style={styles.panelMeta}>{hasDraft ? 'Unpublished draft available' : 'Matches published version'}</Text>
          </View>
          <View style={[styles.reviewDot, hasDraft ? styles.reviewDraft : styles.reviewPublished]} />
        </View>
        <View style={styles.settingsForm}>
          <Field label="Brand subtitle"><TextInput maxLength={120} onChangeText={setSubtitle} style={styles.textInput} value={subtitle} /></Field>
          <Field label="Safety message"><TextInput maxLength={240} multiline onChangeText={setSafetyMessage} style={[styles.textInput, styles.textArea]} textAlignVertical="top" value={safetyMessage} /></Field>
          <Field label="Featured case IDs"><TextInput autoCapitalize="none" onChangeText={setFeaturedIds} placeholder="case-id-one, case-id-two" placeholderTextColor="#98A2B3" style={styles.textInput} value={featuredIds} /></Field>
          <Field label="Recent cases">
            <View style={styles.smallSegment}>{[4, 5, 6].map((value) => <Pressable key={value} onPress={() => setRecentLimit(value)} style={[styles.smallSegmentButton, recentLimit === value && styles.smallSegmentButtonActive]}><Text style={[styles.smallSegmentText, recentLimit === value && styles.smallSegmentTextActive]}>{value}</Text></Pressable>)}</View>
          </Field>
          {message ? <Text style={styles.inlineMessageStandalone}>{message}</Text> : null}
          <View style={styles.editorActions}>
            <Pressable disabled={isSaving || subtitle.trim().length < 10 || safetyMessage.trim().length < 20} onPress={saveDraft} style={[styles.tertiaryButton, (isSaving || subtitle.trim().length < 10 || safetyMessage.trim().length < 20) && styles.buttonDisabled]}><Text style={styles.tertiaryButtonText}>Save draft</Text></Pressable>
            <Pressable disabled={isSaving || !hasDraft} onPress={publish} style={[styles.primaryButton, (!hasDraft || isSaving) && styles.buttonDisabled]}>{isSaving ? <ActivityIndicator color="#FFFFFF" /> : <Text style={styles.primaryButtonText}>Publish</Text>}</Pressable>
          </View>
        </View>
      </View>

      <View style={styles.publishedPreview}>
        <Text style={styles.contentEyebrow}>CURRENTLY PUBLISHED</Text>
        <Text style={styles.previewBrand}>Reward Watch</Text>
        <Text style={styles.previewSubtitle}>{published?.brandSubtitle}</Text>
        <View style={styles.previewSafety}><SymbolView name={{ ios: 'checkmark.shield.fill', android: 'verified_user', web: 'verified_user' }} size={19} tintColor="#5B4DFF" /><Text style={styles.previewSafetyText}>{published?.safetyMessage}</Text></View>
        <View style={styles.previewFacts}><Text style={styles.previewFact}>{published?.recentCaseLimit ?? 4} recent cases</Text><Text style={styles.previewFact}>{published?.featuredCaseIds.length ?? 0} featured</Text></View>
      </View>
    </View>
  );
}

function AuditPanel({ token }: { token: string }) {
  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    fetchAuditLog(token).then(setEntries).catch((requestError: Error) => setError(requestError.message)).finally(() => setIsLoading(false));
  }, [token]);
  if (isLoading) return <CenteredLoader embedded label="Loading audit history" />;
  return (
    <View style={styles.panel}>
      <View style={styles.panelHeader}><View style={styles.panelHeadingCopy}><Text style={styles.panelTitle}>Recent administrative activity</Text><Text style={styles.panelMeta}>{entries.length} events</Text></View></View>
      {error ? <Notice text={error} /> : null}
      <View style={styles.auditList}>{entries.map((entry) => <View key={entry.id} style={styles.auditRow}><View style={styles.auditIcon}><SymbolView name={{ ios: 'pencil.line', android: 'edit', web: 'edit' }} size={16} tintColor="#5B4DFF" /></View><View style={styles.auditCopy}><Text style={styles.auditAction}>{entry.action.replaceAll('.', ' ')}</Text><Text style={styles.auditMeta}>{entry.entityId} · {entry.adminEmail}</Text></View><Text style={styles.auditDate}>{new Date(entry.createdAt).toLocaleString()}</Text></View>)}</View>
    </View>
  );
}

function Field({ children, grow, label }: { children: React.ReactNode; grow?: boolean; label: string }) {
  return <View style={[styles.field, grow && styles.fieldGrow]}><Text style={styles.fieldLabel}>{label}</Text>{children}</View>;
}

function Notice({ text }: { text: string }) {
  return <View style={styles.notice}><SymbolView name={{ ios: 'exclamationmark.circle.fill', android: 'error', web: 'error' }} size={17} tintColor="#B54708" /><Text style={styles.noticeText}>{text}</Text></View>;
}

function CenteredLoader({ embedded, label }: { embedded?: boolean; label: string }) {
  return <SafeAreaView style={embedded ? styles.loaderEmbedded : styles.loaderPage}><ActivityIndicator color="#5B4DFF" /><Text style={styles.loaderText}>{label}</Text></SafeAreaView>;
}

const styles = StyleSheet.create({
  loginPage: { backgroundColor: '#F5F7FB', flex: 1, padding: 24 },
  loginTopBar: { alignSelf: 'center', maxWidth: 1180, width: '100%' },
  backLink: { alignItems: 'center', flexDirection: 'row', gap: 8, paddingVertical: 8 },
  backLinkText: { color: '#5B4DFF', fontSize: 14, fontWeight: '800' },
  loginPanel: { alignSelf: 'center', backgroundColor: '#FFFFFF', borderColor: '#E1E6EF', borderRadius: 12, borderWidth: 1, gap: 18, marginTop: 80, maxWidth: 420, padding: 32, width: '100%', boxShadow: '0 20px 50px rgba(54, 66, 96, 0.10)' },
  adminMark: { alignItems: 'center', backgroundColor: '#6366F1', borderRadius: 10, height: 48, justifyContent: 'center', width: 48 },
  loginHeading: { gap: 5 },
  loginTitle: { color: '#101828', fontSize: 25, fontWeight: '900', lineHeight: 31 },
  loginSubtitle: { color: '#667085', fontSize: 14, fontWeight: '600' },
  field: { gap: 7, minWidth: 0 },
  fieldGrow: { flex: 1 },
  fieldLabel: { color: '#344054', fontSize: 12, fontWeight: '800' },
  fieldHint: { color: '#98A2B3', fontSize: 12, fontWeight: '600', marginTop: 2 },
  textInput: { backgroundColor: '#FFFFFF', borderColor: '#D0D5DD', borderRadius: 8, borderWidth: 1, color: '#101828', fontSize: 14, minHeight: 44, paddingHorizontal: 12, paddingVertical: 10 },
  textArea: { minHeight: 112 },
  noteArea: { minHeight: 74 },
  formError: { color: '#B42318', fontSize: 13, fontWeight: '700' },
  primaryButton: { alignItems: 'center', backgroundColor: '#5B4DFF', borderRadius: 8, justifyContent: 'center', minHeight: 44, paddingHorizontal: 16 },
  primaryButtonText: { color: '#FFFFFF', fontSize: 14, fontWeight: '900' },
  buttonDisabled: { opacity: 0.45 },
  adminPage: { backgroundColor: '#F6F8FB', flex: 1 },
  workspace: { flex: 1, flexDirection: 'row' },
  workspaceCompact: { flexDirection: 'column' },
  sidebar: { backgroundColor: '#FFFFFF', borderRightColor: '#E4E7EC', borderRightWidth: 1, padding: 18, width: 238 },
  sidebarCompact: { borderBottomColor: '#E4E7EC', borderBottomWidth: 1, borderRightWidth: 0, flexDirection: 'row', gap: 12, paddingHorizontal: 16, paddingVertical: 10, width: '100%' },
  sidebarBrand: { alignItems: 'center', flexDirection: 'row', gap: 10, minWidth: 0 },
  sidebarMark: { alignItems: 'center', backgroundColor: '#6366F1', borderRadius: 8, height: 34, justifyContent: 'center', width: 34 },
  sidebarBrandCopy: { flex: 1, minWidth: 0 },
  sidebarTitle: { color: '#101828', fontSize: 14, fontWeight: '900' },
  sidebarMeta: { color: '#98A2B3', fontSize: 10, fontWeight: '800', textTransform: 'uppercase' },
  nav: { gap: 5, marginTop: 32 },
  navCompact: { flexDirection: 'row', marginLeft: 'auto', marginTop: 0 },
  navButton: { alignItems: 'center', borderRadius: 8, flexDirection: 'row', gap: 10, minHeight: 42, paddingHorizontal: 11 },
  navButtonIconOnly: { gap: 0, paddingHorizontal: 10, width: 40 },
  navButtonActive: { backgroundColor: '#F0EFFF' },
  navButtonText: { color: '#667085', fontSize: 13, fontWeight: '800' },
  navButtonTextActive: { color: '#5B4DFF' },
  sidebarFooter: { borderTopColor: '#EAECF0', borderTopWidth: 1, gap: 9, marginTop: 'auto', paddingTop: 15 },
  adminEmail: { color: '#475467', fontSize: 12, fontWeight: '700' },
  signOutButton: { alignItems: 'center', flexDirection: 'row', gap: 8, paddingVertical: 6 },
  signOutText: { color: '#667085', fontSize: 13, fontWeight: '800' },
  adminContent: { alignSelf: 'center', gap: 18, maxWidth: 1380, padding: 26, width: '100%' },
  contentHeader: { alignItems: 'center', flexDirection: 'row', justifyContent: 'space-between' },
  contentEyebrow: { color: '#7F75FF', fontSize: 10, fontWeight: '900' },
  contentTitle: { color: '#101828', fontSize: 28, fontWeight: '900', lineHeight: 35, marginTop: 2 },
  iconButton: { alignItems: 'center', backgroundColor: '#FFFFFF', borderColor: '#E4E7EC', borderRadius: 8, borderWidth: 1, height: 40, justifyContent: 'center', width: 40 },
  sectionStack: { gap: 16 },
  metricsGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 12 },
  adminMetric: { backgroundColor: '#FFFFFF', borderColor: '#E4E7EC', borderRadius: 8, borderWidth: 1, flexGrow: 1, minWidth: 180, padding: 18 },
  metricMarker: { borderRadius: 3, height: 6, marginBottom: 14, width: 28 },
  metricNeutral: { backgroundColor: '#667085' },
  metricWarning: { backgroundColor: '#F79009' },
  metricBlue: { backgroundColor: '#2E90FA' },
  metricGreen: { backgroundColor: '#12B76A' },
  adminMetricValue: { color: '#101828', fontSize: 27, fontWeight: '900', lineHeight: 33 },
  adminMetricLabel: { color: '#667085', fontSize: 12, fontWeight: '700', marginTop: 3 },
  panel: { backgroundColor: '#FFFFFF', borderColor: '#E4E7EC', borderRadius: 8, borderWidth: 1, overflow: 'hidden' },
  panelHeader: { alignItems: 'center', borderBottomColor: '#EAECF0', borderBottomWidth: 1, flexDirection: 'row', justifyContent: 'space-between', padding: 18 },
  panelHeadingCopy: { flex: 1, gap: 3, minWidth: 0 },
  panelTitle: { color: '#101828', fontSize: 16, fontWeight: '900' },
  panelMeta: { color: '#98A2B3', fontSize: 12, fontWeight: '700' },
  securityForm: { alignSelf: 'stretch', gap: 13, maxWidth: 620, padding: 18 },
  securityButton: { alignSelf: 'flex-start', minWidth: 150 },
  securityError: { color: '#B42318', fontSize: 12, fontWeight: '700' },
  securityMessage: { color: '#475467', fontSize: 12, fontWeight: '700' },
  secondaryButton: { alignItems: 'center', backgroundColor: '#F4F3FF', borderRadius: 8, flexDirection: 'row', gap: 7, minHeight: 38, paddingHorizontal: 12 },
  secondaryButtonText: { color: '#5B4DFF', fontSize: 12, fontWeight: '900' },
  inlineMessage: { color: '#475467', fontSize: 12, fontWeight: '700', paddingHorizontal: 18, paddingTop: 12 },
  sourceTable: { paddingHorizontal: 18 },
  sourceRow: { alignItems: 'center', borderBottomColor: '#F2F4F7', borderBottomWidth: 1, flexDirection: 'row', gap: 12, minHeight: 62 },
  healthDot: { borderRadius: 5, height: 9, width: 9 },
  healthGood: { backgroundColor: '#12B76A' },
  healthBad: { backgroundColor: '#F04438' },
  sourceRowCopy: { flex: 1, gap: 2, minWidth: 0 },
  sourceRowName: { color: '#344054', fontSize: 13, fontWeight: '800' },
  sourceRowMeta: { color: '#98A2B3', fontSize: 11, fontWeight: '700' },
  sourceState: { borderRadius: 999, fontSize: 11, fontWeight: '900', overflow: 'hidden', paddingHorizontal: 9, paddingVertical: 5 },
  sourceStateGood: { backgroundColor: '#ECFDF3', color: '#027A48' },
  sourceStateBad: { backgroundColor: '#FEF3F2', color: '#B42318' },
  caseManager: { gap: 14 },
  caseToolbar: { alignItems: 'center', flexDirection: 'row', flexWrap: 'wrap', gap: 12 },
  createButton: { alignItems: 'center', backgroundColor: '#5B4DFF', borderRadius: 8, flexDirection: 'row', gap: 7, minHeight: 44, paddingHorizontal: 14 },
  createButtonText: { color: '#FFFFFF', fontSize: 12, fontWeight: '900' },
  adminSearch: { alignItems: 'center', backgroundColor: '#FFFFFF', borderColor: '#D0D5DD', borderRadius: 8, borderWidth: 1, flex: 1, flexDirection: 'row', gap: 9, minHeight: 44, minWidth: 260, paddingHorizontal: 12 },
  adminSearchInput: { color: '#101828', flex: 1, fontSize: 14, minWidth: 0, paddingVertical: 10 },
  smallSegment: { backgroundColor: '#EAECF0', borderRadius: 8, flexDirection: 'row', padding: 3 },
  smallSegmentButton: { alignItems: 'center', borderRadius: 6, justifyContent: 'center', minHeight: 32, paddingHorizontal: 11 },
  smallSegmentButtonActive: { backgroundColor: '#FFFFFF', boxShadow: '0 1px 3px rgba(16, 24, 40, 0.10)' },
  smallSegmentText: { color: '#667085', fontSize: 12, fontWeight: '800' },
  smallSegmentTextActive: { color: '#344054' },
  caseWorkspace: { alignItems: 'flex-start', flexDirection: 'row', gap: 14 },
  caseWorkspaceCompact: { flexDirection: 'column' },
  caseListPanel: { backgroundColor: '#FFFFFF', borderColor: '#E4E7EC', borderRadius: 8, borderWidth: 1, overflow: 'hidden', width: 440 },
  caseListPanelCompact: { width: '100%' },
  listCountRow: { alignItems: 'center', borderBottomColor: '#EAECF0', borderBottomWidth: 1, flexDirection: 'row', justifyContent: 'space-between', minHeight: 52, paddingHorizontal: 14 },
  listCount: { color: '#344054', fontSize: 13, fontWeight: '900' },
  adminCaseList: { minHeight: 200 },
  adminCaseRow: { alignItems: 'center', borderBottomColor: '#F2F4F7', borderBottomWidth: 1, flexDirection: 'row', gap: 11, minHeight: 82, padding: 11 },
  adminCaseRowSelected: { backgroundColor: '#F7F6FF' },
  adminCaseImage: { backgroundColor: '#EEF2F6', borderRadius: 7, height: 54, width: 48 },
  adminCaseImageFallback: { alignItems: 'center', backgroundColor: '#F2F4F7', borderRadius: 7, height: 54, justifyContent: 'center', width: 48 },
  adminCaseCopy: { flex: 1, gap: 3, minWidth: 0 },
  adminCaseTitle: { color: '#101828', fontSize: 13, fontWeight: '900' },
  adminCaseMeta: { color: '#98A2B3', fontSize: 11, fontWeight: '700' },
  adminCaseFlags: { alignItems: 'center', flexDirection: 'row', gap: 6 },
  miniStatus: { color: '#027A48', fontSize: 10, fontWeight: '900' },
  miniStatusHidden: { color: '#B42318' },
  overrideLabel: { backgroundColor: '#F4F3FF', borderRadius: 999, color: '#5B4DFF', fontSize: 9, fontWeight: '900', overflow: 'hidden', paddingHorizontal: 6, paddingVertical: 2 },
  manualLabel: { backgroundColor: '#E8F7F0', borderRadius: 999, color: '#027A48', fontSize: 9, fontWeight: '900', overflow: 'hidden', paddingHorizontal: 6, paddingVertical: 2 },
  pagination: { flexDirection: 'row', gap: 8, justifyContent: 'flex-end', padding: 12 },
  pageButton: { alignItems: 'center', borderColor: '#D0D5DD', borderRadius: 7, borderWidth: 1, height: 34, justifyContent: 'center', width: 36 },
  editorPanel: { backgroundColor: '#FFFFFF', borderColor: '#E4E7EC', borderRadius: 8, borderWidth: 1, flex: 1, minHeight: 560, minWidth: 0, overflow: 'hidden' },
  editorPanelCompact: { minHeight: 420, width: '100%' },
  editorEmpty: { alignItems: 'center', flex: 1, gap: 9, justifyContent: 'center', minHeight: 360 },
  editorEmptyTitle: { color: '#667085', fontSize: 14, fontWeight: '800' },
  editorContent: { gap: 16, padding: 20 },
  editorHeader: { alignItems: 'center', borderBottomColor: '#EAECF0', borderBottomWidth: 1, flexDirection: 'row', gap: 12, paddingBottom: 15 },
  editorHeaderCopy: { flex: 1, gap: 3, minWidth: 0 },
  editorId: { color: '#101828', fontSize: 16, fontWeight: '900' },
  editorSource: { color: '#667085', fontSize: 12, fontWeight: '700' },
  overrideBadge: { backgroundColor: '#F4F3FF', borderRadius: 999, color: '#5B4DFF', fontSize: 10, fontWeight: '900', overflow: 'hidden', paddingHorizontal: 9, paddingVertical: 5 },
  draftBadge: { backgroundColor: '#FFF4E5', borderRadius: 999, color: '#B54708', fontSize: 10, fontWeight: '900', overflow: 'hidden', paddingHorizontal: 9, paddingVertical: 5 },
  editorNotice: { alignItems: 'flex-start', backgroundColor: '#F8FAFC', borderColor: '#E4E7EC', borderRadius: 8, borderWidth: 1, flexDirection: 'row', gap: 10, padding: 13 },
  editorNoticeText: { color: '#475467', flex: 1, fontSize: 12, fontWeight: '700', lineHeight: 18 },
  publishRow: { alignItems: 'center', backgroundColor: '#F8FAFC', borderRadius: 8, flexDirection: 'row', padding: 13 },
  publishCopy: { flex: 1 },
  editorTwoColumns: { flexDirection: 'row', flexWrap: 'wrap', gap: 12 },
  chipRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  statusChoice: { backgroundColor: '#F8FAFC', borderColor: '#E4E7EC', borderRadius: 999, borderWidth: 1, paddingHorizontal: 11, paddingVertical: 8 },
  statusChoiceActive: { backgroundColor: '#F4F3FF', borderColor: '#C7C2FF' },
  statusChoiceText: { color: '#667085', fontSize: 11, fontWeight: '800' },
  statusChoiceTextActive: { color: '#5B4DFF' },
  formDivider: { backgroundColor: '#EAECF0', height: 1, marginVertical: 2 },
  formSectionTitle: { color: '#101828', fontSize: 13, fontWeight: '900' },
  galleryRow: { gap: 9 },
  galleryChoice: { borderColor: 'transparent', borderRadius: 8, borderWidth: 2, padding: 2 },
  galleryChoiceSelected: { borderColor: '#5B4DFF' },
  galleryImage: { backgroundColor: '#EEF2F6', borderRadius: 5, height: 76, width: 68 },
  uploadedImageWrap: { position: 'relative' },
  removePhotoButton: { alignItems: 'center', backgroundColor: '#344054', borderRadius: 12, height: 24, justifyContent: 'center', position: 'absolute', right: -5, top: -5, width: 24 },
  editorActions: { alignItems: 'center', borderTopColor: '#EAECF0', borderTopWidth: 1, flexDirection: 'row', gap: 10, justifyContent: 'flex-end', paddingTop: 16 },
  tertiaryButton: { alignItems: 'center', borderColor: '#D0D5DD', borderRadius: 8, borderWidth: 1, justifyContent: 'center', minHeight: 44, paddingHorizontal: 14 },
  tertiaryButtonText: { color: '#475467', fontSize: 12, fontWeight: '900' },
  deleteButton: { alignItems: 'center', borderColor: '#FDA29B', borderRadius: 8, borderWidth: 1, justifyContent: 'center', minHeight: 44, paddingHorizontal: 14 },
  deleteButtonConfirm: { backgroundColor: '#D92D20', borderColor: '#D92D20' },
  deleteButtonText: { color: '#B42318', fontSize: 12, fontWeight: '900' },
  deleteButtonTextConfirm: { color: '#FFFFFF' },
  settingsLayout: { alignItems: 'flex-start', flexDirection: 'row', flexWrap: 'wrap', gap: 14 },
  settingsPanel: { flex: 2, minWidth: 320 },
  settingsForm: { gap: 16, minWidth: 0, padding: 18 },
  reviewDot: { borderRadius: 6, height: 12, width: 12 },
  reviewDraft: { backgroundColor: '#F79009' },
  reviewPublished: { backgroundColor: '#12B76A' },
  inlineMessageStandalone: { color: '#475467', fontSize: 12, fontWeight: '700' },
  publishedPreview: { backgroundColor: '#F8FAFC', borderColor: '#E4E7EC', borderRadius: 8, borderWidth: 1, flex: 1, gap: 12, minWidth: 280, padding: 22 },
  previewBrand: { color: '#101828', fontSize: 24, fontWeight: '900' },
  previewSubtitle: { color: '#667085', fontSize: 14, fontWeight: '600', lineHeight: 20 },
  previewSafety: { alignItems: 'flex-start', backgroundColor: '#FFFFFF', borderColor: '#E4E7EC', borderRadius: 8, borderWidth: 1, flexDirection: 'row', gap: 10, marginTop: 8, padding: 13 },
  previewSafetyText: { color: '#475467', flex: 1, fontSize: 12, fontWeight: '700', lineHeight: 18 },
  previewFacts: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  previewFact: { backgroundColor: '#EAECF0', borderRadius: 999, color: '#475467', fontSize: 10, fontWeight: '900', overflow: 'hidden', paddingHorizontal: 8, paddingVertical: 5 },
  auditList: { paddingHorizontal: 18 },
  auditRow: { alignItems: 'center', borderBottomColor: '#F2F4F7', borderBottomWidth: 1, flexDirection: 'row', gap: 11, minHeight: 66 },
  auditIcon: { alignItems: 'center', backgroundColor: '#F4F3FF', borderRadius: 7, height: 32, justifyContent: 'center', width: 32 },
  auditCopy: { flex: 1, gap: 2, minWidth: 0 },
  auditAction: { color: '#344054', fontSize: 12, fontWeight: '900', textTransform: 'capitalize' },
  auditMeta: { color: '#98A2B3', fontSize: 11, fontWeight: '700' },
  auditDate: { color: '#667085', fontSize: 11, fontWeight: '700' },
  notice: { alignItems: 'center', backgroundColor: '#FFFAEB', borderColor: '#FEDF89', borderRadius: 8, borderWidth: 1, flexDirection: 'row', gap: 9, padding: 12 },
  noticeText: { color: '#B54708', flex: 1, fontSize: 12, fontWeight: '700' },
  loaderPage: { alignItems: 'center', backgroundColor: '#F6F8FB', flex: 1, gap: 10, justifyContent: 'center' },
  loaderEmbedded: { alignItems: 'center', backgroundColor: 'transparent', gap: 10, justifyContent: 'center', minHeight: 220 },
  loaderText: { color: '#667085', fontSize: 13, fontWeight: '700' },
});
