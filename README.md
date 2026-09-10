# 🏠 NidoControl

**Sistema web local para la gestión, seguimiento diario y entrega segura de niños en nidos y guarderías pequeñas de Quillabamba.**

---

## 📋 Descripción

NidoControl es un sistema web desarrollado con Django y Python para la gestión de guarderías pequeñas. Permite:

- 👶 Gestión de niños y apoderados
- ✅ Control de asistencia, ingreso y salida
- 👤 Registro de personas autorizadas para recoger niños
- 📝 Bitácora digital diaria
- ⚠️ Registro de incidencias
- 📊 Dashboard con indicadores clave
- 📈 Estadísticas con gráficos interactivos
- 📄 Generación de reportes en PDF
- ⚙️ Configuración del sistema
- 🌙 Modo oscuro

---

## 📑 Índice

- [Requisitos Previos](#-requisitos-previos)
- [Instalación en Windows](#-instalación-en-windows)
- [Instalación en Linux](#-instalación-en-linux)
- [Comandos Rápidos](#-comandos-rápidos)
- [Tecnologías](#️-tecnologías)
- [Solución de Problemas](#-solución-de-problemas)

---

## 🚀 Requisitos Previos

Estos requisitos son **comunes para Windows y Linux**:

| Requisito | Versión mínima | Descripción |
|-----------|----------------|-------------|
| **Python** | 3.8+ | Lenguaje de programación |
| **pip** | Última | Gestor de paquetes de Python |
| **Git** | Última | Control de versiones |

---

## 🪟 INSTALACIÓN EN WINDOWS

### Requisitos específicos Windows

- Windows 10 o superior
- 4 GB de RAM mínimo
- 500 MB de espacio libre

### Paso 1: Instalar Python

1. Ve a: https://www.python.org/downloads/windows/
2. Descarga el instalador de **Python 3.11** o superior
3. **MUY IMPORTANTE:** En la primera pantalla del instalador, marca la casilla:
   - Add Python to PATH
4. Clic en Install Now
5. Espera a que termine

Verificar instalación — Abre CMD (Presiona Win + R, escribe cmd, Enter) y escribe:
python --version
pip --version

text

Deberías ver algo como:
Python 3.11.5
pip 23.2.1

text

### Paso 2: Instalar Git

1. Ve a: https://git-scm.com/download/win
2. Descarga el instalador
3. Ejecuta y acepta las opciones por defecto
4. Verifica en CMD:
git --version

text

### Paso 3: Clonar el repositorio

Abre CMD y ejecuta:
cd %USERPROFILE%\Documents
git clone https://github.com/TU-USUARIO/Nido-control.git
cd Nido-control

text

### Paso 4: Crear entorno virtual
python -m venv venv
venv\Scripts\activate

text

Deberías ver (venv) al inicio de la línea.

### Paso 5: Instalar dependencias
pip install --upgrade pip
pip install -r requirements.txt

text

### Paso 6: Crear la base de datos
python manage.py makemigrations
python manage.py migrate

text

### Paso 7: Crear superusuario
python manage.py createsuperuser

text

Responde:
- Username: admin
- Email: admin@nidocontrol.com
- Password: admin123

### Paso 8: Ejecutar el servidor
python manage.py runserver

text

### Paso 9: Abrir en el navegador
http://127.0.0.1:8000

text

### Solución de Problemas en Windows

| Error | Solución |
|-------|----------|
| 'python' no se reconoce | Reinstala Python marcando "Add Python to PATH" |
| 'pip' no se reconoce | Ejecuta: python -m ensurepip --upgrade |
| Puerto 8000 ocupado | Usa otro puerto: python manage.py runserver 8080 |
| No se ven estilos CSS | Recarga con Ctrl + Shift + R |

---

## 🐧 INSTALACIÓN EN LINUX

### Distribuciones soportadas

- openSUSE Leap 15+ (probado)
- Ubuntu 20.04+
- Debian 11+
- Fedora 35+
- Linux Mint 20+
- Arch Linux / Manjaro

### Requisitos específicos Linux

- 4 GB de RAM mínimo
- 500 MB de espacio libre
- Acceso a sudo (para instalar paquetes)

### Paso 1: Instalar Python, pip, venv y Git

openSUSE Leap:
sudo zypper refresh
sudo zypper install python3 python3-pip python3-devel python3-venv git

text

Ubuntu / Debian / Linux Mint:
sudo apt update
sudo apt install python3 python3-pip python3-venv python3-dev git

text

Fedora:
sudo dnf install python3 python3-pip python3-devel git

text

Arch Linux / Manjaro:
sudo pacman -S python python-pip git

text

### Paso 2: Verificar la instalación
python3 --version
pip3 --version
git --version

text

### Paso 3: Clonar el repositorio
cd ~/Documentos
git clone https://github.com/TU-USUARIO/Nido-control.git
cd Nido-control

text

### Paso 4: Crear entorno virtual
python3 -m venv venv
source venv/bin/activate

text

Deberías ver (venv) al inicio.

### Paso 5: Instalar dependencias
pip install --upgrade pip
pip install -r requirements.txt

text

Si tienes errores con mysqlclient:
openSUSE
sudo zypper install gcc python3-devel mysql-devel

Ubuntu / Debian
sudo apt install gcc python3-dev default-libmysqlclient-dev build-essential

Fedora
sudo dnf install gcc python3-devel mysql-devel

text

### Paso 6: Crear la base de datos
python manage.py makemigrations
python manage.py migrate

text

### Paso 7: Crear superusuario
python manage.py createsuperuser

text

### Paso 8: Ejecutar el servidor
python manage.py runserver

text

### Paso 9: Abrir en el navegador
http://127.0.0.1:8000

text

### Solución de Problemas en Linux

| Error | Solución |
|-------|----------|
| python3-venv no instalado | sudo zypper install python3-venv (openSUSE) / sudo apt install python3-venv (Ubuntu) |
| Permission denied al clonar | chmod -R 755 ~/Nido-control |
| No module named django | source venv/bin/activate |
| Puerto 8000 ocupado | python manage.py runserver 8080 |

---

## 🎯 Comandos Rápidos

### 🐧 Linux

Activar entorno virtual:
cd ~/Nido-control
source venv/bin/activate

text

Ejecutar servidor:
python manage.py runserver

text

Desactivar entorno virtual:
deactivate

text

### 🪟 Windows

Activar entorno virtual:
cd %USERPROFILE%\Documents\Nido-control
venv\Scripts\activate

text

Ejecutar servidor:
python manage.py runserver

text

---

## 🛠️ Tecnologías

- Backend: Django 6.1+, Python 3.13
- Frontend: HTML5, CSS3, Bootstrap 5, JavaScript
- Base de Datos: SQLite
- Gráficos: Chart.js
- Reportes: ReportLab (PDF)

---

## 📁 Estructura del Proyecto
Nido-control/
├── core/ # Aplicación principal
├── nidocontrol/ # Configuración del proyecto
├── static/ # Archivos estáticos
├── media/ # Archivos subidos
├── templates/ # Templates globales
├── manage.py # Script de gestión
├── requirements.txt # Dependencias
└── README.md # Este archivo

text

---

## 👥 Roles del Sistema

| Rol | Permisos |
|-----|----------|
| Administrador | Acceso completo a todas las funcionalidades |
| Cuidadora | Gestión de niños, asistencia, bitácora e incidencias |

---

## 📊 Funcionalidades

| Módulo | Descripción |
|--------|-------------|
| Dashboard | Panel con indicadores clave |
| Niños | Registro completo, datos del apoderado |
| Asistencia | Ingreso/salida, estados |
| Bitácora | Alimentación, descanso, ánimo |
| Incidencias | Registro y seguimiento |
| Estadísticas | Gráficos circulares y de barras |
| Reportes | PDF de asistencia, incidencias, bitácora |
| Configuración | Aulas, usuarios, perfil |

---

## 🔄 Actualizar el Proyecto
git add .
git commit -m "Descripción del cambio"
git push

text

---

## 📝 Licencia

Este proyecto es de uso educativo y está desarrollado para la gestión de guarderías.

---

## 👨‍💻 Desarrollador

- Equipo - Estudiante de Computación e Informática
- Año: 2026

---

**NidoControl - Gestión sencilla, cuidado organizado y entrega segura**