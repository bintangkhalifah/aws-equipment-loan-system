CREATE TABLE IF NOT EXISTS loans (
  id INT AUTO_INCREMENT PRIMARY KEY,
  equipment_name VARCHAR(100) NOT NULL,
  borrower_name VARCHAR(100) NOT NULL,
  loan_date DATE NOT NULL,
  return_date DATE NULL,
  status ENUM('borrowed','returned') NOT NULL DEFAULT 'borrowed'
);
