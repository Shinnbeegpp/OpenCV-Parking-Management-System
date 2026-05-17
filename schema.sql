-- ParkEase Parking Management System
-- Run this in MySQL Workbench before starting the application

CREATE DATABASE IF NOT EXISTS parkease;
USE parkease;

-- Admin accounts (created directly in MySQL)
CREATE TABLE IF NOT EXISTS admins (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Staff accounts (created by admin via app)
CREATE TABLE IF NOT EXISTS staff (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(100) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    is_flagged BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by INT,
    FOREIGN KEY (created_by) REFERENCES admins(id)
);

-- Parking transactions
CREATE TABLE IF NOT EXISTS transactions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    transaction_id VARCHAR(20) UNIQUE NOT NULL,
    plate_number VARCHAR(20) NOT NULL,
    vehicle_type VARCHAR(50) NOT NULL,
    time_in TIMESTAMP NOT NULL,
    time_out TIMESTAMP NULL,
    date_in DATE NOT NULL,
    staff_entry_id INT,
    staff_exit_id INT,
    duration_minutes INT NULL,
    total_charge DECIMAL(10,2) NULL,
    status ENUM('active','completed','unknown') DEFAULT 'active',
    is_flagged BOOLEAN DEFAULT FALSE,
    FOREIGN KEY (staff_entry_id) REFERENCES staff(id),
    FOREIGN KEY (staff_exit_id) REFERENCES staff(id)
);

-- Activity logs
CREATE TABLE IF NOT EXISTS activity_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    log_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    user_type ENUM('admin','staff') NOT NULL,
    user_id INT NOT NULL,
    username VARCHAR(50) NOT NULL,
    action VARCHAR(100) NOT NULL,
    details TEXT
);

-- Shift records (blind drop)
CREATE TABLE IF NOT EXISTS shifts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    staff_id INT NOT NULL,
    shift_start TIMESTAMP NOT NULL,
    shift_end TIMESTAMP NULL,
    system_revenue DECIMAL(10,2) DEFAULT 0.00,
    staff_reported_revenue DECIMAL(10,2) NULL,
    is_flagged BOOLEAN DEFAULT FALSE,
    FOREIGN KEY (staff_id) REFERENCES staff(id)
);

-- Default admin account (password: admin123 - change after setup)
-- Password hash for 'admin123'
INSERT IGNORE INTO admins (username, password_hash, full_name)
VALUES ('admin', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMlJbekRSjelMnFHMKlpDNJH4K', 'System Administrator');

-- Note: To create additional admin accounts, use fix_admin.py or generate
-- a bcrypt hash in Python and insert it directly:
--   import bcrypt
--   hash = bcrypt.hashpw(b'yourpassword', bcrypt.gensalt()).decode()
-- INSERT INTO admins (username, password_hash, full_name)
-- VALUES ('yourusername', '<bcrypt_hash>', 'Your Name');
-- Settings table (single row, stores all system config)
CREATE TABLE IF NOT EXISTS settings (
    id INT PRIMARY KEY DEFAULT 1,
    parking_capacity INT DEFAULT 50,
    rate_type ENUM('hourly', 'flat', 'daily_max') DEFAULT 'hourly',
    rate_per_hour DECIMAL(10,2) DEFAULT 10.00,
    flat_rate DECIMAL(10,2) DEFAULT 10.00,
    daily_max_rate DECIMAL(10,2) DEFAULT 100.00,
    minimum_charge DECIMAL(10,2) DEFAULT 10.00,
    overstay_hours INT DEFAULT 24,
    entry_camera_index INT DEFAULT 0,
    exit_camera_index INT DEFAULT 1,
    demo_video_path VARCHAR(500) DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- Insert default settings
INSERT IGNORE INTO settings (id) VALUES (1);

-- Blacklist table
CREATE TABLE IF NOT EXISTS blacklist (
    id INT AUTO_INCREMENT PRIMARY KEY,
    plate_number VARCHAR(20) UNIQUE NOT NULL,
    reason TEXT,
    added_by INT NOT NULL,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    FOREIGN KEY (added_by) REFERENCES admins(id)
);

-- Migrations for existing databases (safe to re-run)
ALTER TABLE settings ADD COLUMN IF NOT EXISTS entry_camera_index INT DEFAULT 0;
ALTER TABLE settings ADD COLUMN IF NOT EXISTS exit_camera_index INT DEFAULT 1;
ALTER TABLE settings ADD COLUMN IF NOT EXISTS demo_video_path VARCHAR(500) DEFAULT '';
ALTER TABLE shifts ADD COLUMN IF NOT EXISTS is_resolved BOOLEAN DEFAULT FALSE;

-- Reserved/monthly vehicles
CREATE TABLE IF NOT EXISTS reserved_vehicles (
    id INT AUTO_INCREMENT PRIMARY KEY,
    plate_number VARCHAR(20) UNIQUE NOT NULL,
    owner_name VARCHAR(100) NOT NULL,
    contact_number VARCHAR(20),
    monthly_fee DECIMAL(10,2) DEFAULT 0.00,
    start_date DATE NOT NULL,
    expiry_date DATE NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    added_by_type ENUM('admin', 'staff') NOT NULL,
    added_by INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);