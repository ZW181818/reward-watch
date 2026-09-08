export type AdminMapCoordinate = {
  latitude: number;
  longitude: number;
};

export type AdminLocationMapProps = {
  coordinate: AdminMapCoordinate | null;
  onCoordinateChange: (coordinate: AdminMapCoordinate) => void;
};
