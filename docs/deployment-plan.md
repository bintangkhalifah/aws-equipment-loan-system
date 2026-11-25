# Deployment Plan

Langkah-langkah untuk membuat ulang sistem peminjaman barang (Track A: EC2 + RDS MySQL) dari nol di AWS Academy Cloud Foundations Sandbox, region **us-east-1**. Semua resource di sandbox dihapus otomatis setiap hari, jadi dokumen ini dipakai untuk mengulang pembuatan.

Diagram arsitektur: [`architecture.png`](architecture.png)

## Ringkasan resource

| Resource | Nama | Catatan |
| --- | --- | --- |
| VPC | `loan-vpc` | 10.0.0.0/16, 2 subnet publik + 2 subnet privat (us-east-1a dan us-east-1b), tanpa NAT |
| Internet Gateway | `loan-igw` | Terpasang ke `loan-vpc` |
| Security group web | `web-sg` | Inbound SSH 22 dan TCP 5000 dari My IP |
| Security group DB | `db-sg` | Inbound MySQL 3306 hanya dari `web-sg` |
| DB subnet group | `loan-db-subnet` | Dua subnet privat (syarat RDS minimal 2 AZ) |
| RDS | `loan-db` | MySQL 8.4, db.t3.micro, Single-AZ, us-east-1a, Publicly accessible: No |
| EC2 | `loan-web` | t3.micro, Amazon Linux 2023, subnet publik us-east-1a |
| IAM | `LabInstanceProfile` (LabRole) | Bawaan sandbox |

## Prasyarat

- Lab AWS Academy sudah dimulai (status hijau) dan konsol AWS terbuka di region **us-east-1**.
- Key pair `vockey` dan file `labsuser.pem` sudah diunduh dari AWS Academy.
- Tahu IP publik sendiri (opsi **My IP** di security group akan mengisinya otomatis).

## Langkah 1: VPC

1. Buka **VPC > Create VPC > VPC and more**.
2. Isi:
   - Name tag auto-generation: `loan`
   - IPv4 CIDR: `10.0.0.0/16`
   - Number of AZs: 2
   - Public subnets: 2, Private subnets: 2
   - NAT gateways: **None**
   - VPC endpoints: **None**
3. Create VPC. Wizard otomatis membuat `loan-vpc`, `loan-igw`, subnet, dan route table.
4. Cek di tab **Resource map** bahwa subnet publik terhubung ke route table dengan rute ke IGW, dan subnet privat tidak.

## Langkah 2: Security group

Nama security group tidak boleh diawali `sg-`.

1. `web-sg` di `loan-vpc`, inbound:
   - SSH, TCP 22, source **My IP**
   - Custom TCP, port 5000, source **My IP**
2. `db-sg` di `loan-vpc`, inbound:
   - MYSQL/Aurora, TCP 3306, source **`web-sg`** (pilih security group, bukan IP)

## Langkah 3: RDS MySQL

1. **RDS > Subnet groups > Create DB subnet group**: nama `loan-db-subnet`, VPC `loan-vpc`, AZ us-east-1a dan us-east-1b, pilih **dua subnet privat**.
2. **Create database > Standard create > MySQL**, lalu isi:
   - DB instance identifier: `loan-db`
   - Instance class: `db.t3.micro`, Single-AZ (tanpa standby)
   - Master username: `admin`, password dibuat sendiri dan **tidak disimpan di repo**
   - Authentication: **Password authentication** (jangan pilih Kerberos, akan error "Directory required")
   - VPC `loan-vpc`, DB subnet group `loan-db-subnet`
   - **Public access: No**
   - Security group: `db-sg`
   - Availability Zone: us-east-1a
   - Additional configuration > Initial database name: `loansdb`
3. Tunggu status **Available** (beberapa menit), lalu catat **Endpoint** dari tab Connectivity.

## Langkah 4: EC2

1. **EC2 > Launch instance**, lalu isi:
   - Name: `loan-web`
   - AMI: Amazon Linux 2023, instance type `t3.micro`
   - Key pair: `vockey`
   - Network: `loan-vpc`, subnet **publik us-east-1a**, Auto-assign public IP: **Enable**
   - Security group: pilih yang sudah ada, `web-sg`
   - Storage: gp2
   - Advanced details: IAM instance profile `LabInstanceProfile`, Credit specification `Standard`
2. Launch, tunggu status **Running** dan 2/2 checks passed, lalu catat **Public IPv4 address**.

## Langkah 5: Masuk ke EC2 lewat SSH

Di Terminal Mac (bukan di EC2):

```bash
mkdir -p ~/.ssh
mv ~/Downloads/labsuser.pem ~/.ssh/labsuser.pem
chmod 400 ~/.ssh/labsuser.pem
ssh -i ~/.ssh/labsuser.pem ec2-user@<PUBLIC-IP-EC2>
```

File `.pem` tidak boleh masuk repo (sudah ada di `.gitignore`).

## Langkah 6: Cek koneksi EC2 ke RDS

Di dalam EC2, pasang dulu klien MySQL, git, dan `nc`, lalu uji port:

```bash
sudo dnf install -y mariadb105 git nmap-ncat
nc -zv <RDS-ENDPOINT> 3306
```

Hasil yang diharapkan: koneksi ke port 3306 berhasil. Ini membuktikan `db-sg` mengizinkan `web-sg`.

## Langkah 7: Siapkan database dan aplikasi

Di dalam EC2:

```bash
git clone https://github.com/bintangkhalifah/aws-equipment-loan-system.git
cd aws-equipment-loan-system
sudo dnf install -y python3-pip
pip3 install -r requirements.txt
mysql -h <RDS-ENDPOINT> -u admin -p loansdb < schema.sql
```

Cek tabel:

```bash
mysql -h <RDS-ENDPOINT> -u admin -p loansdb -e "SHOW TABLES; DESCRIBE loans;"
```

## Langkah 8: Jalankan API

Variabel koneksi database mengikuti `.env.example`: `DB_HOST`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`. Password dimasukkan lewat `read -s` supaya tidak tampil di layar:

```bash
export DB_HOST=<RDS-ENDPOINT>
export DB_USER=admin
export DB_NAME=loansdb
read -s DB_PASSWORD && export DB_PASSWORD
nohup python3 app.py > app.log 2>&1 &
```

## Langkah 9: Pengujian

Dijalankan di dalam EC2, jadi alamatnya `localhost`.

```bash
curl http://localhost:5000/health

curl -X POST http://localhost:5000/loans \
  -H "Content-Type: application/json" \
  -d '{"equipment_name":"Proyektor","borrower_name":"Andi","loan_date":"2026-11-25"}'

curl http://localhost:5000/loans

curl -X PUT http://localhost:5000/loans/1 \
  -H "Content-Type: application/json" \
  -d '{"status":"returned","return_date":"2026-11-26"}'

curl -X DELETE http://localhost:5000/loans/1
```

Hasil yang diharapkan:

| Endpoint | Respons |
| --- | --- |
| GET /health | `{"db_ok": 1}` |
| POST /loans | `{"id": ...}` |
| GET /loans | Daftar peminjaman |
| PUT /loans/1 | `{"updated": 1}` |
| DELETE /loans/1 | `{"deleted": 1}` |

Pengujian lewat browser di komputer sendiri: buka `http://<PUBLIC-IP-EC2>:5000/health` dan `http://<PUBLIC-IP-EC2>:5000/loans` dari IP yang sama dengan yang dipakai di `web-sg`.

## Bukti yang diambil

| No | Bukti |
| --- | --- |
| 01 | VPC resource map |
| 02 | Inbound rules `web-sg` |
| 03 | Inbound rules `db-sg` |
| 04 | RDS status Creating |
| 05 | EC2 Running |
| 06 | Tab Security EC2 |
| 07 | RDS Available dan endpoint |
| 08 | SSH berhasil ke EC2 |
| 09 | `nc` ke RDS port 3306 |
| 10 | Tabel `loans` di MySQL |
| 12 | `/health` dari CLI |
| 13 | Uji CRUD dari CLI |
| 14 | `/health` di browser |
| 15 | `/loans` di browser |
| 16 | Pengecekan resource lewat AWS CLI dari EC2 (`describe-instances`, `describe-db-instances`, `describe-security-groups`) |

## Catatan keamanan

- RDS tidak punya akses publik dan hanya menerima koneksi dari `web-sg`.
- Akses SSH dan port 5000 dibatasi ke IP pemilik (My IP).
- Password database tidak ada di repo, layar, atau screenshot.
- IP publik EC2 hanya berlaku selama instance berjalan dan berubah jika instance dihentikan lalu dijalankan lagi.

## Membersihkan resource

Sandbox menghapus semua resource otomatis pada pukul 00:00. Untuk menghapus lebih awal: hapus RDS `loan-db` (tanpa final snapshot), terminate EC2 `loan-web`, hapus DB subnet group, lalu hapus VPC `loan-vpc` (otomatis menghapus subnet dan IGW terkait).
