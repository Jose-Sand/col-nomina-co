```markdown
# 🧮 nomina-co

### Calculadora de nómina electrónica Colombia

![Python](https://img.shields.io/badge/python-3.8+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![DIAN](https://img.shields.io/badge/DIAN-Resolución%20000013-orange.svg)

Librería Python para calcular nómina electrónica en Colombia según normativa vigente. Calcula prestaciones sociales (cesantías, prima, vacaciones), aportes al Sistema de Seguridad Social Integral (PILA), retención en la fuente y genera archivos XML compatibles con la DIAN.

## 🎯 ¿Por qué nomina-co?

Los errores en liquidaciones de nómina cuestan dinero real a PyMEs colombianas y pueden generar sanciones de la DIAN. La mayoría de soluciones disponibles:

- ❌ No están actualizadas con las tablas 2024 (UVT, salario mínimo)
- ❌ No cumplen con la resolución 000013 de nómina electrónica
- ❌ Cobran licencias costosas para pequeñas empresas
- ❌ No tienen soporte para casos comunes (salario integral, horas extras, incapacidades)

**nomina-co** es una solución open source, actualizada y enfocada en el ecosistema colombiano.

## ✨ Características

- ✅ **Prestaciones sociales**: Cálculo de cesantías, prima de servicios y vacaciones según Código Sustantivo del Trabajo
- ✅ **Aportes PILA**: Salud (12.5%), pensión (16%), ARL según nivel de riesgo (I-V)
- ✅ **Retención en la fuente**: Tabla 2024 con UVT actualizado (47.065 COP)
- ✅ **XML nómina electrónica DIAN**: Generación conforme a resolución 000013 de 2021
- ✅ **Salario integral**: Soporte completo con factor 1.3
- ✅ **Horas extras y recargos**: Diurnos, nocturnos, dominicales, festivos
- ✅ **Incapacidades**: Común, profesional, licencias de maternidad/paternidad
- ✅ **Liquidación final**: Cálculo completo para terminación de contratos

## 📦 Instalación

```bash
pip install nomina-co
```

O para desarrollo:

```bash
git clone https://github.com/tu-usuario/nomina-co.git
cd nomina-co
pip install -e .
```

## 🚀 Uso básico

### Liquidación de nómina mensual

```python
from nomina_co import Empleado, LiquidacionNomina
from datetime import date

# Crear empleado
empleado = Empleado(
    identificacion="1234567890",
    nombre="Juan Pérez",
    salario_base=2500000,
    cargo="Desarrollador",
    fecha_ingreso=date(2023, 1, 15)
)

# Liquidar nómina del mes
liquidacion = LiquidacionNomina(empleado)
resultado = liquidacion.liquidar_mes(year=2024, mes=3)

print(f"Salario base: ${resultado.devengado:,.0f}")
print(f"Aportes salud: ${resultado.aporte_salud:,.0f}")
print(f"Aportes pensión: ${resultado.aporte_pension:,.0f}")
print(f"Retención fuente: ${resultado.retencion:,.0f}")
print(f"Total a pagar: ${resultado.neto:,.0f}")
```

### Cálculo de prestaciones sociales

```python
from nomina_co import CalculadoraPrestaciones
from datetime import date

calculadora = CalculadoraPrestaciones(
    salario_base=2500000,
    auxilio_transporte=True,
    fecha_ingreso=date(2023, 1, 15)
)

# Cesantías acumuladas
cesantias = calculadora.calcular_cesantias(fecha_corte=date(2024, 3, 31))
print(f"Cesantías: ${cesantias:,.0f}")

# Prima de servicios (semestre)
prima = calculadora.calcular_prima(semestre=1, year=2024)
print(f"Prima: ${prima:,.0f}")

# Vacaciones (días a disfrutar)
vacaciones = calculadora.calcular_vacaciones(dias=15)
print(f"Vacaciones 15 días: ${vacaciones:,.0f}")
```

### Aportes seguridad social (PILA)

```python
from nomina_co import CalculadoraAportes

aportes = CalculadoraAportes(
    salario_base=2500000,
    nivel_riesgo_arl=1  # Riesgo mínimo
)

detalle = aportes.calcular_aportes_mes()

print(f"Salud (12.5%): ${detalle['salud']:,.0f}")
print(f"  - Empleado (4%): ${detalle['salud_empleado']:,.0f}")
print(f"  - Empleador (8.5%): ${detalle['salud_empleador']:,.0f}")
print(f"Pensión (16%): ${detalle['pension']:,.0f}")
print(f"ARL: ${detalle['arl']:,.0f}")
```

### Retención en la fuente

```python
from nomina_co import CalculadoraRetencion

retencion = CalculadoraRetencion(
    salario_base=8000000,
    deducciones_mensuales={
        'medicina_prepagada': 500000,
        'dependientes': 2  # Número de dependientes
    }
)

valor_retencion = retencion.calcular_retencion_mes()
print(f"Retención en la fuente: ${valor_retencion:,.0f}")
```

### Generar XML nómina electrónica DIAN

```python
from nomina_co import GeneradorXMLDian
from datetime import date

generador = GeneradorXMLDian(
    empresa_nit="900123456-7",
    empresa_razon_social="Mi Empresa SAS",
    ambiente="produccion"  # o "pruebas"
)

xml_content = generador.generar_xml(
    empleado=empleado,
    resultado_liquidacion=resultado,
    periodo=date(2024, 3, 1),
    consecutivo="NOM-2024-03-001"
)

# Guardar XML
with open("nomina_electronica.xml", "w", encoding="utf-8") as f:
    f.write(xml_content)
```

### Liquidación final (terminación de contrato)

```python
from nomina_co import LiquidacionFinal

liquidador = LiquidacionFinal(
    empleado=empleado,
    fecha_retiro=date(2024, 3, 31),
    motivo="renuncia"  # renuncia, despido_justo, despido_injusto
)

liquidacion_final = liquidador.calcular()

print(f"Cesantías: ${liquidacion_final.cesantias:,.0f}")
print(f"Intereses cesantías: ${liquidacion_final.intereses_cesantias:,.0f}")
print(f"Prima proporcional: ${liquidacion_final.prima:,.0f}")
print(f"Vacaciones: ${liquidacion_final.vacaciones:,.0f}")
print(f"Indemnización: ${liquidacion_final.indemnizacion:,.0f}")
print(f"TOTAL: ${liquidacion_final.total:,.0f}")
```

## 📁 Estructura del proyecto

```
nomina-co/
├── src/
│   └── nomina_co/
│       ├── __init__.py           # Exportaciones públicas
│       ├── modelos.py            # Clases de datos (Empleado, Liquidación)
│       ├── liquidacion.py        # Lógica principal de liquidación
│       ├── aportes.py            # Cálculo aportes PILA
│       ├── retencion.py          # Retención en la fuente
│       └── xml_dian.py           # Generación XML nómina electrónica
├── tests/
│   └── test_liquidacion.py       # Tests unitarios
├── pyproject.toml                # Configuración del proyecto
└── README.md
```

## 🔧 Configuración avanzada

### Valores personalizados

```python
from nomina_co import config

# Actualizar valor UVT (se actualiza anualmente)
config.UVT_2024 = 47065

# Salario mínimo 2024
config.SALARIO_MINIMO_2024 = 1300000

# Auxilio de transporte 2024
config.AUXILIO_TRANSPORTE_2024 = 162000
```

### Horas extras y recargos

```python
from nomina_co import CalculadoraExtras

extras = CalculadoraExtras(salario_base=2500000)

# Horas extras diurnas (25%)
he_diurnas = extras.calcular_horas_extras_diurnas(horas=10)

# Horas extras nocturnas (75%)
he_nocturnas = extras.calcular_horas_extras_nocturnas(horas=5)

# Recargo nocturno (35%)
recargo_nocturno = extras.calcular_recargo_nocturno(horas=8)

# Dominical/festivo (75%)
dominical = extras.calcular_dominical(dias=2)
```

## 🧪 Tests

```bash
# Ejecutar tests
pytest tests/

# Con cobertura
pytest --cov=nomina_co tests/
```

## 📚 Normativa aplicada

Esta librería implementa:

- **Código Sustantivo del Trabajo** (Decreto Ley 2663 de 1950)
- **Ley 50 de 1990** - Reforma laboral
- **Ley 100 de 1993** - Sistema de Seguridad Social Integral
- **Decreto 1772 de 1994** - Aportes parafiscales
- **Resolución DIAN 000013 de 2021** - Nómina electrónica
- **Estatuto Tributario** - Retención en la fuente (art. 383 y siguientes)
- **UVT 2024**: $47.065 (Resolución DIAN 000220 de 2023)
- **Salario mínimo 2024**: $1.300.000

## 🤝 Contribuir

¡Las contribuciones son bienvenidas! Este proyecto busca ser la referencia open source para nómina en Colombia.

1. Fork el proyecto
2. Crea tu rama de feature (`git checkout -b feature/nueva-funcionalidad`)
3. Commit tus cambios (`git commit -am 'Agrega nueva funcionalidad'`)
4. Push a la rama (`git push origin feature/nueva-funcionalidad`)
5. Abre un Pull Request

### Áreas de contribución

- ✅ Actualización de tablas anuales (UVT, salario mínimo)
- ✅ Casos especiales (trabajadores rurales, empleadas domésticas)
- ✅ Integración con APIs de bancos para pagos
- ✅ Mejoras en generación XML DIAN
- ✅ Documentación y ejemplos

## ⚠️ Disclaimer

Esta librería es una herramienta de apoyo. Siempre verifica los cálculos con un contador o abogado laboral. Las leyes y normativas pueden cambiar. El autor no se hace responsable por errores en liquidaciones.

## 📄 Licencia

MIT License - ver archivo [LICENSE](LICENSE) para más detalles.

## 💬 Soporte

- **Issues**: [GitHub Issues](https://github.com/tu-usuario/nomina-co/issues)
- **Discusiones**: [GitHub Discussions](https://github.com/tu-usuario/nomina-co/discussions)
- **Email**: tu-email@ejemplo.com

---

Hecho con ❤️ para PyMEs y developers colombianos

**Tags**: #nomina #colombia #dian #pila #retencion #prestaciones-sociales #python #payroll #rrhh
```