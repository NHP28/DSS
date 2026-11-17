CREATE TABLE IF NOT EXISTS users (
  id INT PRIMARY KEY,
  display_name VARCHAR(100) NOT NULL
) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS pois (
  id INT PRIMARY KEY,
  name VARCHAR(255) NOT NULL,
  category ENUM('cafe','restaurant','hotel','tourist_spot') NOT NULL,
  latitude DOUBLE NOT NULL,
  longitude DOUBLE NOT NULL,
  district VARCHAR(100) NOT NULL,
  rating DOUBLE NOT NULL,
  price_avg DOUBLE NOT NULL,
  popularity DOUBLE NOT NULL,
  INDEX idx_category (category),
  INDEX idx_district (district)
) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS checkins (
  user_id INT NOT NULL,
  poi_id INT NOT NULL,
  timestamp_sec BIGINT NOT NULL,
  local_hour TINYINT UNSIGNED NOT NULL,
  local_weekday TINYINT UNSIGNED NOT NULL,
  PRIMARY KEY (user_id, poi_id, timestamp_sec),
  FOREIGN KEY (user_id) REFERENCES users(id),
  FOREIGN KEY (poi_id) REFERENCES pois(id),
  INDEX idx_hour_poi (local_hour, poi_id)
) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS feedback (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  user_id INT NOT NULL,
  poi_id INT NOT NULL,
  action ENUM('like','dislike','visit') NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id),
  FOREIGN KEY (poi_id) REFERENCES pois(id),
  INDEX idx_feedback_user (user_id, created_at)
) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS dataset_meta (
  id TINYINT PRIMARY KEY,
  sha256 CHAR(64) NOT NULL
) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
