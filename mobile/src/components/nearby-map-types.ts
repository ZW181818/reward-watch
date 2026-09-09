export type MapCoordinate = {
  latitude: number;
  longitude: number;
};

export type MapSearchOrigin = MapCoordinate & {
  accuracy?: number;
  kind: 'device' | 'map';
};

export type NearbyMapPoint = MapCoordinate & {
  approximate: boolean;
  caseId: string;
  label: string;
  precision: 'city' | 'region';
  reward: number | null;
  title: string;
};

export type NearbyMapLabels = {
  caseLocation: string;
  clusterCases: string;
  mapUnavailable: string;
  yourLocation: string;
  searchCenter: string;
};

export type NearbyMapProps = {
  labels: NearbyMapLabels;
  onCenterChange: (coordinate: MapCoordinate) => void;
  onSelectCase: (caseId: string, coordinate: MapCoordinate) => void;
  onSelectCases: (caseIds: string[]) => void;
  origin: MapSearchOrigin | null;
  points: NearbyMapPoint[];
  radiusKm: number;
  selectedCaseId: string | null;
  selectedCoordinate: MapCoordinate | null;
};
