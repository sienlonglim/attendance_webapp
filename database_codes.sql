DROP TABLE IF EXISTS students;

CREATE TABLE IF NOT EXISTS students (
	student_id INT NOT NULL AUTO_INCREMENT,
	student_name VARCHAR(50) NOT NULL,
	class VARCHAR(50) NOT NULL,
	cohort_year YEAR NOT NULL DEFAULT 2023,
	PRIMARY KEY(student_id)
);

LOAD DATA INFILE 'F:/Natuyuki/Dropbox/Gitstuff/scraping_attendance/database/namelist.csv' INTO TABLE students FIELDS
TERMINATED BY ',' OPTIONALLY ENCLOSED BY '\"' LINES TERMINATED BY '\n' IGNORE 1 ROWS;