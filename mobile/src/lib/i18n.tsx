import AsyncStorage from '@react-native-async-storage/async-storage';
import {
  createContext,
  type ReactNode,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react';
import { Platform } from 'react-native';

export type LanguageCode = 'en' | 'zh' | 'fr' | 'es';

export const languageOptions: { code: LanguageCode; label: string; shortLabel: string }[] = [
  { code: 'en', label: 'English', shortLabel: 'EN' },
  { code: 'zh', label: '中文', shortLabel: '中文' },
  { code: 'fr', label: 'Français', shortLabel: 'FR' },
  { code: 'es', label: 'Español', shortLabel: 'ES' },
];

const en = {
  all: 'All',
  allCases: 'All Cases',
  allMarkets: 'All markets',
  allProvinces: 'All provinces',
  allSources: 'All sources',
  allStates: 'All states',
  aliases: 'Aliases',
  age: 'Age',
  apiConnectionUnavailable: 'API connection unavailable',
  apiLoadHint: 'The public notice service did not respond successfully.',
  browseCases: 'Browse cases',
  canada: 'Canada',
  casePhotos: 'Case photos',
  caseSummary: 'Case summary',
  caseUnavailable: 'Case unavailable',
  cases: 'Cases',
  casesSubtitle: 'Search official notices by country, state or province, status, and reward amount.',
  chooseCountry: 'Choose country',
  chooseLanguage: 'Choose language',
  chooseValue: 'Choose {label}',
  clear: 'Clear',
  closePhotoViewer: 'Close photo viewer',
  closed: 'Closed',
  country: 'Country',
  dataChecked: 'Data checked',
  dateOfBirthUsed: 'Date of birth used',
  emptyCasesBody: 'Try clearing the search term or broadening the country, region, or status filters.',
  emptyCasesTitle: 'No cases match these filters',
  emptyHomeBody: 'Try a broader keyword or switch back to all North America notices.',
  emptyHomeTitle: 'No cases match this search',
  eyes: 'Eyes',
  featuredCases: 'Featured Cases',
  hair: 'Hair',
  height: 'Height',
  highestReward: 'Highest reward',
  highestRewards: 'Highest Rewards',
  home: 'Home',
  homeSubtitle: 'Official public reward notices across North America',
  identifyingFeatures: 'Identifying features',
  imageUnavailable: 'Image unavailable',
  informationRequested: 'Information Requested',
  language: 'Language',
  learnMore: 'Learn more',
  loadMoreCases: 'Load more cases',
  loadingAllCases: 'Loading all cases',
  loadingCaseDetails: 'Loading case details',
  loadingCases: 'Loading cases',
  loadingSavedCases: 'Loading saved cases',
  marketsCovered: 'Markets covered',
  nationality: 'Nationality',
  newest: 'Newest',
  nextPhoto: 'Next photo',
  noSavedCasesBody: 'Open a case detail page and select Save case to keep it here.',
  noSavedCasesTitle: 'No saved cases yet',
  notPublished: 'Not published',
  officialCaseInformation: 'Official case information',
  officialNotice: 'Official Notice',
  officialRewardNotice: 'Official reward notice',
  officialSource: 'Official source',
  officialSourceWarning: 'Official source warning',
  officialSources: 'Official sources ({count})',
  open: 'Open',
  openOfficialSource: 'Open official source from {source}',
  openPhoto: 'Open photo {current} of {total}',
  photoCounter: '{current} of {total}',
  placeOfBirth: 'Place of birth',
  possibleCommunities: 'Possible communities',
  previousPhoto: 'Previous photo',
  province: 'Province',
  publicReward: 'Public reward',
  published: 'Published',
  race: 'Race',
  rankedByReward: 'Ranked by public reward amount',
  recentCases: 'Recent Cases',
  reset: 'Reset',
  resetFilters: 'Reset filters',
  result: 'result',
  results: 'results',
  retryPhoto: 'Retry photo {current} of {total}',
  reward: 'Reward',
  rewardHighToLow: 'Reward high to low',
  rewardLowToHigh: 'Reward low to high',
  safetyMessage: 'Do not approach any individual. Submit information directly to the official source.',
  saveCase: 'Save case',
  saved: 'Saved',
  savedCases: 'Saved Cases',
  savedCasesSubtitle: 'Cases saved locally on this device. No account or cloud sync is used.',
  searchAllCases: 'Search all cases',
  searchAllPlaceholder: 'Search titles, sources, locations or summaries',
  searchCases: 'Search cases',
  searchPlaceholder: 'Search cases, sources or keywords',
  selectedByEditors: 'Selected by Reward Watch editors',
  sex: 'Sex',
  showPhoto: 'Show photo {number}',
  showingResults: 'Showing {visible} of {total}',
  sort: 'Sort',
  source: 'Source',
  sourceAttribution: 'Source attribution',
  sourceUpdated: 'Source updated',
  state: 'State',
  status: 'Status',
  tapToRetry: 'Tap to retry',
  titleAZ: 'Title A-Z',
  unableToLoadCases: 'Unable to load cases',
  unableToLoadMore: 'Unable to load more cases',
  unableToLoadSaved: 'Unable to load saved cases',
  us: 'US',
  viewAllCases: 'View all cases',
  viewAllPhotos: 'View all {count}',
  viewPhoto: 'View photo',
  visibleCases: 'Visible cases',
  weight: 'Weight',
} as const;

export type TranslationKey = keyof typeof en;

const translations: Record<LanguageCode, Record<TranslationKey, string>> = {
  en,
  zh: {
    all: '全部', allCases: '全部案件', allMarkets: '全部地区', allProvinces: '全部省份', allSources: '全部来源', allStates: '全部州', aliases: '别名', age: '年龄', apiConnectionUnavailable: '暂时无法连接数据服务', apiLoadHint: '公开悬赏信息服务未能正常响应。', browseCases: '浏览案件', canada: '加拿大', casePhotos: '案件图片', caseSummary: '案件摘要', caseUnavailable: '案件暂不可用', cases: '案件', casesSubtitle: '按国家、州或省、状态与悬赏金额查找官方公开信息。', chooseCountry: '选择国家', chooseLanguage: '选择语言', chooseValue: '选择{label}', clear: '清除', closePhotoViewer: '关闭图片浏览器', closed: '已关闭', country: '国家', dataChecked: '数据核验', dateOfBirthUsed: '使用的出生日期', emptyCasesBody: '请清除搜索词，或扩大国家、地区及状态筛选范围。', emptyCasesTitle: '没有符合筛选条件的案件', emptyHomeBody: '请尝试更宽泛的关键词，或切换回全部北美公开信息。', emptyHomeTitle: '没有匹配的案件', eyes: '眼睛', featuredCases: '精选案件', hair: '头发', height: '身高', highestReward: '最高悬赏', highestRewards: '最高悬赏', home: '首页', homeSubtitle: '汇集北美官方公开悬赏信息', identifyingFeatures: '识别特征', imageUnavailable: '图片暂不可用', informationRequested: '征集线索', language: '语言', learnMore: '了解更多', loadMoreCases: '加载更多案件', loadingAllCases: '正在加载全部案件', loadingCaseDetails: '正在加载案件详情', loadingCases: '正在加载案件', loadingSavedCases: '正在加载收藏案件', marketsCovered: '覆盖市场', nationality: '国籍', newest: '最新发布', nextPhoto: '下一张图片', noSavedCasesBody: '打开案件详情并选择“收藏案件”，即可保存在这里。', noSavedCasesTitle: '暂无收藏案件', notPublished: '未公布', officialCaseInformation: '官方案件信息', officialNotice: '官方公告', officialRewardNotice: '官方悬赏说明', officialSource: '官方来源', officialSourceWarning: '官方来源警告', officialSources: '官方来源（{count}）', open: '进行中', openOfficialSource: '打开{source}的官方来源', openPhoto: '打开第 {current} 张图片，共 {total} 张', photoCounter: '第 {current} 张，共 {total} 张', placeOfBirth: '出生地', possibleCommunities: '可能出现的社区', previousPhoto: '上一张图片', province: '省份', publicReward: '公开悬赏', published: '发布日期', race: '族裔', rankedByReward: '按公开悬赏金额排序', recentCases: '最近案件', reset: '重置', resetFilters: '重置筛选', result: '条结果', results: '条结果', retryPhoto: '重试第 {current} 张图片，共 {total} 张', reward: '悬赏', rewardHighToLow: '悬赏从高到低', rewardLowToHigh: '悬赏从低到高', safetyMessage: '请勿接近任何个人。请直接向官方来源提交信息。', saveCase: '收藏案件', saved: '已收藏', savedCases: '收藏案件', savedCasesSubtitle: '案件仅保存在本设备，不需要账号，也不会进行云同步。', searchAllCases: '搜索全部案件', searchAllPlaceholder: '搜索标题、来源、地点或摘要', searchCases: '搜索案件', searchPlaceholder: '搜索案件、来源或关键词', selectedByEditors: '由 Reward Watch 编辑精选', sex: '性别', showPhoto: '显示第 {number} 张图片', showingResults: '已显示 {visible} / {total}', sort: '排序', source: '来源', sourceAttribution: '来源说明', sourceUpdated: '来源更新', state: '州', status: '状态', tapToRetry: '点击重试', titleAZ: '标题 A-Z', unableToLoadCases: '无法加载案件', unableToLoadMore: '无法加载更多案件', unableToLoadSaved: '无法加载收藏案件', us: '美国', viewAllCases: '查看全部案件', viewAllPhotos: '查看全部 {count} 张', viewPhoto: '查看图片', visibleCases: '可见案件', weight: '体重',
  },
  fr: {
    all: 'Tous', allCases: 'Toutes les affaires', allMarkets: 'Tous les marchés', allProvinces: 'Toutes les provinces', allSources: 'Toutes les sources', allStates: 'Tous les États', aliases: 'Alias', age: 'Âge', apiConnectionUnavailable: 'Service de données indisponible', apiLoadHint: 'Le service des avis publics n’a pas répondu correctement.', browseCases: 'Parcourir les affaires', canada: 'Canada', casePhotos: 'Photos de l’affaire', caseSummary: 'Résumé de l’affaire', caseUnavailable: 'Affaire indisponible', cases: 'Affaires', casesSubtitle: 'Recherchez les avis officiels par pays, État ou province, statut et montant.', chooseCountry: 'Choisir le pays', chooseLanguage: 'Choisir la langue', chooseValue: 'Choisir : {label}', clear: 'Effacer', closePhotoViewer: 'Fermer la galerie', closed: 'Fermée', country: 'Pays', dataChecked: 'Données vérifiées', dateOfBirthUsed: 'Date de naissance utilisée', emptyCasesBody: 'Effacez la recherche ou élargissez les filtres de pays, de région ou de statut.', emptyCasesTitle: 'Aucune affaire ne correspond aux filtres', emptyHomeBody: 'Essayez un mot-clé plus large ou revenez à tous les avis nord-américains.', emptyHomeTitle: 'Aucune affaire trouvée', eyes: 'Yeux', featuredCases: 'Affaires à la une', hair: 'Cheveux', height: 'Taille', highestReward: 'Récompense maximale', highestRewards: 'Récompenses maximales', home: 'Accueil', homeSubtitle: 'Avis officiels de récompense publique en Amérique du Nord', identifyingFeatures: 'Signes distinctifs', imageUnavailable: 'Image indisponible', informationRequested: 'Informations recherchées', language: 'Langue', learnMore: 'En savoir plus', loadMoreCases: 'Charger plus d’affaires', loadingAllCases: 'Chargement de toutes les affaires', loadingCaseDetails: 'Chargement des détails', loadingCases: 'Chargement des affaires', loadingSavedCases: 'Chargement des favoris', marketsCovered: 'Marchés couverts', nationality: 'Nationalité', newest: 'Plus récentes', nextPhoto: 'Photo suivante', noSavedCasesBody: 'Ouvrez une affaire et sélectionnez Enregistrer pour la conserver ici.', noSavedCasesTitle: 'Aucune affaire enregistrée', notPublished: 'Non publiée', officialCaseInformation: 'Informations officielles', officialNotice: 'Avis officiel', officialRewardNotice: 'Avis officiel de récompense', officialSource: 'Source officielle', officialSourceWarning: 'Avertissement de la source officielle', officialSources: 'Sources officielles ({count})', open: 'Ouverte', openOfficialSource: 'Ouvrir la source officielle de {source}', openPhoto: 'Ouvrir la photo {current} sur {total}', photoCounter: '{current} sur {total}', placeOfBirth: 'Lieu de naissance', possibleCommunities: 'Communautés possibles', previousPhoto: 'Photo précédente', province: 'Province', publicReward: 'Récompense publique', published: 'Publication', race: 'Origine', rankedByReward: 'Classées par montant de récompense publique', recentCases: 'Affaires récentes', reset: 'Réinitialiser', resetFilters: 'Réinitialiser les filtres', result: 'résultat', results: 'résultats', retryPhoto: 'Réessayer la photo {current} sur {total}', reward: 'Récompense', rewardHighToLow: 'Récompense décroissante', rewardLowToHigh: 'Récompense croissante', safetyMessage: 'N’approchez aucune personne. Transmettez vos informations directement à la source officielle.', saveCase: 'Enregistrer', saved: 'Enregistrées', savedCases: 'Affaires enregistrées', savedCasesSubtitle: 'Les affaires sont enregistrées localement sur cet appareil, sans compte ni synchronisation.', searchAllCases: 'Rechercher toutes les affaires', searchAllPlaceholder: 'Rechercher des titres, sources, lieux ou résumés', searchCases: 'Rechercher des affaires', searchPlaceholder: 'Rechercher des affaires, sources ou mots-clés', selectedByEditors: 'Sélection de la rédaction Reward Watch', sex: 'Sexe', showPhoto: 'Afficher la photo {number}', showingResults: '{visible} affichées sur {total}', sort: 'Trier', source: 'Source', sourceAttribution: 'Attribution de la source', sourceUpdated: 'Source mise à jour', state: 'État', status: 'Statut', tapToRetry: 'Appuyer pour réessayer', titleAZ: 'Titre A-Z', unableToLoadCases: 'Impossible de charger les affaires', unableToLoadMore: 'Impossible de charger plus d’affaires', unableToLoadSaved: 'Impossible de charger les favoris', us: 'États-Unis', viewAllCases: 'Voir toutes les affaires', viewAllPhotos: 'Voir les {count} photos', viewPhoto: 'Voir la photo', visibleCases: 'Affaires visibles', weight: 'Poids',
  },
  es: {
    all: 'Todos', allCases: 'Todos los casos', allMarkets: 'Todos los mercados', allProvinces: 'Todas las provincias', allSources: 'Todas las fuentes', allStates: 'Todos los estados', aliases: 'Alias', age: 'Edad', apiConnectionUnavailable: 'Servicio de datos no disponible', apiLoadHint: 'El servicio de avisos públicos no respondió correctamente.', browseCases: 'Explorar casos', canada: 'Canadá', casePhotos: 'Fotos del caso', caseSummary: 'Resumen del caso', caseUnavailable: 'Caso no disponible', cases: 'Casos', casesSubtitle: 'Busca avisos oficiales por país, estado o provincia, estado del caso y recompensa.', chooseCountry: 'Elegir país', chooseLanguage: 'Elegir idioma', chooseValue: 'Elegir {label}', clear: 'Borrar', closePhotoViewer: 'Cerrar galería', closed: 'Cerrado', country: 'País', dataChecked: 'Datos verificados', dateOfBirthUsed: 'Fecha de nacimiento utilizada', emptyCasesBody: 'Borra la búsqueda o amplía los filtros de país, región o estado.', emptyCasesTitle: 'Ningún caso coincide con los filtros', emptyHomeBody: 'Prueba una palabra más amplia o vuelve a todos los avisos de Norteamérica.', emptyHomeTitle: 'No hay casos coincidentes', eyes: 'Ojos', featuredCases: 'Casos destacados', hair: 'Cabello', height: 'Estatura', highestReward: 'Mayor recompensa', highestRewards: 'Mayores recompensas', home: 'Inicio', homeSubtitle: 'Avisos oficiales de recompensas públicas en Norteamérica', identifyingFeatures: 'Rasgos identificativos', imageUnavailable: 'Imagen no disponible', informationRequested: 'Información solicitada', language: 'Idioma', learnMore: 'Más información', loadMoreCases: 'Cargar más casos', loadingAllCases: 'Cargando todos los casos', loadingCaseDetails: 'Cargando detalles del caso', loadingCases: 'Cargando casos', loadingSavedCases: 'Cargando casos guardados', marketsCovered: 'Mercados cubiertos', nationality: 'Nacionalidad', newest: 'Más recientes', nextPhoto: 'Foto siguiente', noSavedCasesBody: 'Abre un caso y selecciona Guardar caso para conservarlo aquí.', noSavedCasesTitle: 'Aún no hay casos guardados', notPublished: 'No publicada', officialCaseInformation: 'Información oficial del caso', officialNotice: 'Aviso oficial', officialRewardNotice: 'Aviso oficial de recompensa', officialSource: 'Fuente oficial', officialSourceWarning: 'Advertencia de la fuente oficial', officialSources: 'Fuentes oficiales ({count})', open: 'Abierto', openOfficialSource: 'Abrir la fuente oficial de {source}', openPhoto: 'Abrir foto {current} de {total}', photoCounter: '{current} de {total}', placeOfBirth: 'Lugar de nacimiento', possibleCommunities: 'Comunidades posibles', previousPhoto: 'Foto anterior', province: 'Provincia', publicReward: 'Recompensa pública', published: 'Publicado', race: 'Raza', rankedByReward: 'Ordenadas por recompensa pública', recentCases: 'Casos recientes', reset: 'Restablecer', resetFilters: 'Restablecer filtros', result: 'resultado', results: 'resultados', retryPhoto: 'Reintentar foto {current} de {total}', reward: 'Recompensa', rewardHighToLow: 'Recompensa de mayor a menor', rewardLowToHigh: 'Recompensa de menor a mayor', safetyMessage: 'No se acerque a ninguna persona. Envíe la información directamente a la fuente oficial.', saveCase: 'Guardar caso', saved: 'Guardados', savedCases: 'Casos guardados', savedCasesSubtitle: 'Los casos se guardan localmente en este dispositivo, sin cuenta ni sincronización.', searchAllCases: 'Buscar todos los casos', searchAllPlaceholder: 'Buscar títulos, fuentes, lugares o resúmenes', searchCases: 'Buscar casos', searchPlaceholder: 'Buscar casos, fuentes o palabras clave', selectedByEditors: 'Selección editorial de Reward Watch', sex: 'Sexo', showPhoto: 'Mostrar foto {number}', showingResults: 'Mostrando {visible} de {total}', sort: 'Ordenar', source: 'Fuente', sourceAttribution: 'Atribución de la fuente', sourceUpdated: 'Fuente actualizada', state: 'Estado', status: 'Estado', tapToRetry: 'Toca para reintentar', titleAZ: 'Título A-Z', unableToLoadCases: 'No se pudieron cargar los casos', unableToLoadMore: 'No se pudieron cargar más casos', unableToLoadSaved: 'No se pudieron cargar los casos guardados', us: 'Estados Unidos', viewAllCases: 'Ver todos los casos', viewAllPhotos: 'Ver las {count} fotos', viewPhoto: 'Ver foto', visibleCases: 'Casos visibles', weight: 'Peso',
  },
};

const languageLocales: Record<LanguageCode, string> = {
  en: 'en-US',
  zh: 'zh-CN',
  fr: 'fr-CA',
  es: 'es-US',
};

const storageKey = 'reward-watch.language';

type TranslationParams = Record<string, number | string>;

type LanguageContextValue = {
  formatDate: (value: string) => string;
  language: LanguageCode;
  locale: string;
  setLanguage: (language: LanguageCode) => void;
  t: (key: TranslationKey, params?: TranslationParams) => string;
};

const LanguageContext = createContext<LanguageContextValue | null>(null);

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [language, setLanguageState] = useState<LanguageCode>('en');
  const locale = languageLocales[language];

  useEffect(() => {
    AsyncStorage.getItem(storageKey)
      .then((storedLanguage) => {
        if (languageOptions.some((option) => option.code === storedLanguage)) {
          setLanguageState(storedLanguage as LanguageCode);
        }
      })
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    if (Platform.OS === 'web' && typeof document !== 'undefined') {
      document.documentElement.lang = language;
    }
  }, [language]);

  const value = useMemo<LanguageContextValue>(() => {
    const dateFormatter = new Intl.DateTimeFormat(locale, {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
    });

    return {
      formatDate: (rawValue) => {
        const parsedDate = new Date(`${rawValue}T00:00:00`);
        return Number.isNaN(parsedDate.getTime()) ? rawValue : dateFormatter.format(parsedDate);
      },
      language,
      locale,
      setLanguage: (nextLanguage) => {
        setLanguageState(nextLanguage);
        AsyncStorage.setItem(storageKey, nextLanguage).catch(() => undefined);
      },
      t: (key, params) => interpolate(translations[language][key], params),
    };
  }, [language, locale]);

  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>;
}

export function useLanguage() {
  const context = useContext(LanguageContext);

  if (!context) {
    throw new Error('useLanguage must be used within LanguageProvider');
  }

  return context;
}

export function getLocalizedStatus(status: string, t: LanguageContextValue['t']) {
  if (status === 'Open') return t('open');
  if (status === 'Closed') return t('closed');
  if (status === 'Information Requested') return t('informationRequested');
  return status;
}

export function getLocalizedCountry(country: 'All' | 'Canada' | 'US', t: LanguageContextValue['t']) {
  if (country === 'All') return t('all');
  if (country === 'Canada') return t('canada');
  return t('us');
}

function interpolate(value: string, params?: TranslationParams) {
  if (!params) return value;

  return Object.entries(params).reduce(
    (result, [key, replacement]) => result.replaceAll(`{${key}}`, String(replacement)),
    value
  );
}
