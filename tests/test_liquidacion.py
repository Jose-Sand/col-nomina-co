"""
Tests unitarios para liquidación de prestaciones sociales colombianas

Cubre casos de:
- Cesantías (mensual y anual)
- Prima de servicios (semestral)
- Vacaciones
- Salario integral
- Horas extras y recargos
- Liquidación final con todos los conceptos
- Casos edge: periodos incompletos, ausencias, incapacidades
"""

import unittest
from datetime import date, datetime
from decimal import Decimal

from nomina_co.liquidacion import (
    LiquidacionPrestaciones,
    EmpleadoLiquidacion,
    ConceptoDevengado,
    TipoConcepto,
    TipoHoraExtra,
)


class TestEmpleadoLiquidacion(unittest.TestCase):
    """Tests para modelo de empleado en liquidación"""

    def test_empleado_basico(self):
        """Verifica creación de empleado con datos básicos"""
        empleado = EmpleadoLiquidacion(
            identificacion="1234567890",
            nombre="Juan Pérez",
            salario_base=Decimal("1300000"),
            fecha_ingreso=date(2023, 1, 1),
            es_salario_integral=False,
        )

        self.assertEqual(empleado.identificacion, "1234567890")
        self.assertEqual(empleado.salario_base, Decimal("1300000"))
        self.assertFalse(empleado.es_salario_integral)

    def test_empleado_salario_integral(self):
        """Verifica empleado con salario integral"""
        empleado = EmpleadoLiquidacion(
            identificacion="9876543210",
            nombre="María García",
            salario_base=Decimal("15000000"),
            fecha_ingreso=date(2022, 6, 15),
            es_salario_integral=True,
        )

        self.assertTrue(empleado.es_salario_integral)
        self.assertEqual(empleado.salario_base, Decimal("15000000"))


class TestConceptosDevengados(unittest.TestCase):
    """Tests para conceptos devengados adicionales"""

    def test_concepto_auxilio_transporte(self):
        """Verifica auxilio de transporte como concepto"""
        concepto = ConceptoDevengado(
            tipo=TipoConcepto.AUXILIO_TRANSPORTE,
            valor=Decimal("140606"),
            descripcion="Auxilio de transporte 2024",
        )

        self.assertEqual(concepto.tipo, TipoConcepto.AUXILIO_TRANSPORTE)
        self.assertEqual(concepto.valor, Decimal("140606"))

    def test_concepto_hora_extra_diurna(self):
        """Verifica hora extra diurna"""
        concepto = ConceptoDevengado(
            tipo=TipoConcepto.HORA_EXTRA,
            valor=Decimal("81250"),
            cantidad_horas=Decimal("10"),
            tipo_hora_extra=TipoHoraExtra.DIURNA,
            descripcion="10 horas extras diurnas",
        )

        self.assertEqual(concepto.cantidad_horas, Decimal("10"))
        self.assertEqual(concepto.tipo_hora_extra, TipoHoraExtra.DIURNA)

    def test_concepto_hora_extra_nocturna(self):
        """Verifica hora extra nocturna"""
        concepto = ConceptoDevengado(
            tipo=TipoConcepto.HORA_EXTRA,
            valor=Decimal("112500"),
            cantidad_horas=Decimal("8"),
            tipo_hora_extra=TipoHoraExtra.NOCTURNA,
            descripcion="8 horas extras nocturnas",
        )

        self.assertEqual(concepto.tipo_hora_extra, TipoHoraExtra.NOCTURNA)

    def test_concepto_recargo_nocturno(self):
        """Verifica recargo nocturno"""
        concepto = ConceptoDevengado(
            tipo=TipoConcepto.RECARGO_NOCTURNO,
            valor=Decimal("48750"),
            cantidad_horas=Decimal("15"),
            descripcion="Recargo nocturno",
        )

        self.assertEqual(concepto.tipo, TipoConcepto.RECARGO_NOCTURNO)


class TestCesantiasMensuales(unittest.TestCase):
    """Tests para cálculo de cesantías mensuales"""

    def setUp(self):
        """Configuración común para tests de cesantías"""
        self.liquidador = LiquidacionPrestaciones()

    def test_cesantias_mes_completo(self):
        """Calcula cesantías para mes completo con salario básico"""
        empleado = EmpleadoLiquidacion(
            identificacion="1111111111",
            nombre="Pedro López",
            salario_base=Decimal("1300000"),
            fecha_ingreso=date(2024, 1, 1),
        )

        cesantias = self.liquidador.calcular_cesantias_mes(
            empleado=empleado,
            fecha_corte=date(2024, 1, 31),
        )

        # Cesantías = (salario * 30) / 360
        esperado = (Decimal("1300000") * 30) / 360
        self.assertEqual(cesantias, esperado.quantize(Decimal("0.01")))

    def test_cesantias_con_auxilio_transporte(self):
        """Cesantías incluyen auxilio de transporte"""
        empleado = EmpleadoLiquidacion(
            identificacion="2222222222",
            nombre="Ana Martínez",
            salario_base=Decimal("1300000"),
            fecha_ingreso=date(2024, 1, 1),
        )

        conceptos = [
            ConceptoDevengado(
                tipo=TipoConcepto.AUXILIO_TRANSPORTE,
                valor=Decimal("140606"),
            )
        ]

        cesantias = self.liquidador.calcular_cesantias_mes(
            empleado=empleado,
            fecha_corte=date(2024, 1, 31),
            conceptos_adicionales=conceptos,
        )

        base = Decimal("1300000") + Decimal("140606")
        esperado = (base * 30) / 360
        self.assertEqual(cesantias, esperado.quantize(Decimal("0.01")))

    def test_cesantias_con_horas_extras(self):
        """Cesantías incluyen promedio de horas extras"""
        empleado = EmpleadoLiquidacion(
            identificacion="3333333333",
            nombre="Carlos Ruiz",
            salario_base=Decimal("2000000"),
            fecha_ingreso=date(2023, 7, 1),
        )

        # 6 meses de historia con horas extras
        conceptos = [
            ConceptoDevengado(
                tipo=TipoConcepto.HORA_EXTRA,
                valor=Decimal("500000"),  # Promedio mensual últimos 6 meses
            )
        ]

        cesantias = self.liquidador.calcular_cesantias_mes(
            empleado=empleado,
            fecha_corte=date(2024, 1, 31),
            conceptos_adicionales=conceptos,
        )

        base = Decimal("2000000") + Decimal("500000")
        esperado = (base * 30) / 360
        self.assertEqual(cesantias, esperado.quantize(Decimal("0.01")))

    def test_cesantias_salario_integral_no_aplica(self):
        """Empleados con salario integral ya tienen cesantías incluidas"""
        empleado = EmpleadoLiquidacion(
            identificacion="4444444444",
            nombre="Laura Gómez",
            salario_base=Decimal("15000000"),
            fecha_ingreso=date(2023, 1, 1),
            es_salario_integral=True,
        )

        cesantias = self.liquidador.calcular_cesantias_mes(
            empleado=empleado,
            fecha_corte=date(2024, 1, 31),
        )

        # Salario integral ya incluye prestaciones, retorna 0
        self.assertEqual(cesantias, Decimal("0"))


class TestCesantiasAnuales(unittest.TestCase):
    """Tests para cesantías anuales (acumulado año)"""

    def setUp(self):
        self.liquidador = LiquidacionPrestaciones()

    def test_cesantias_ano_completo(self):
        """Cesantías para año completo trabajado"""
        empleado = EmpleadoLiquidacion(
            identificacion="5555555555",
            nombre="Diego Herrera",
            salario_base=Decimal("1500000"),
            fecha_ingreso=date(2023, 1, 1),
        )

        cesantias = self.liquidador.calcular_cesantias_anuales(
            empleado=empleado,
            fecha_inicio=date(2023, 1, 1),
            fecha_fin=date(2023, 12, 31),
        )

        # Un año completo = salario * 12 / 12 = salario
        esperado = Decimal("1500000")
        self.assertEqual(cesantias, esperado)

    def test_cesantias_periodo_parcial(self):
        """Cesantías por periodo menor a un año"""
        empleado = EmpleadoLiquidacion(
            identificacion="6666666666",
            nombre="Sandra Castro",
            salario_base=Decimal("1800000"),
            fecha_ingreso=date(2023, 7, 15),
        )

        cesantias = self.liquidador.calcular_cesantias_anuales(
            empleado=empleado,
            fecha_inicio=date(2023, 7, 15),
            fecha_fin=date(2023, 12, 31),
        )

        # 168 días trabajados (15 jul a 31 dic)
        # Cesantías = (salario * días) / 360
        dias = 168
        esperado = (Decimal("1800000") * dias) / 360
        self.assertAlmostEqual(float(cesantias), float(esperado), places=2)

    def test_cesantias_con_variacion_salarial(self):
        """Cesantías con aumentos salariales durante el año"""
        empleado = EmpleadoLiquidacion(
            identificacion="7777777777",
            nombre="Roberto Díaz",
            salario_base=Decimal("2500000"),  # Salario final
            fecha_ingreso=date(2023, 1, 1),
        )

        # Simula aumentos promediando salarios
        salario_promedio = Decimal("2200000")  # Promedio del año

        cesantias = self.liquidador.calcular_cesantias_anuales(
            empleado=empleado,
            fecha_inicio=date(2023, 1, 1),
            fecha_fin=date(2023, 12, 31),
            salario_promedio=salario_promedio,
        )

        esperado = salario_promedio  # Año completo
        self.assertEqual(cesantias, esperado)


class TestPrimaServicios(unittest.TestCase):
    """Tests para prima de servicios semestral"""

    def setUp(self):
        self.liquidador = LiquidacionPrestaciones()

    def test_prima_semestre_completo(self):
        """Prima de servicios para semestre completo"""
        empleado = EmpleadoLiquidacion(
            identificacion="8888888888",
            nombre="Patricia Vargas",
            salario_base=Decimal("1600000"),
            fecha_ingreso=date(2023, 1, 1),
        )

        # Primer semestre (enero-junio)
        prima = self.liquidador.calcular_prima_servicios(
            empleado=empleado,
            fecha_inicio=date(2024, 1, 1),
            fecha_fin=date(2024, 6, 30),
        )

        # Prima = (salario * días) / 360, semestre completo = 180 días
        esperado = (Decimal("1600000") * 180) / 360
        self.assertEqual(prima, esperado.quantize(Decimal("0.01")))

    def test_prima_segundo_semestre(self):
        """Prima segundo semestre (julio-diciembre)"""
        empleado = EmpleadoLiquidacion(
            identificacion="9999999999",
            nombre="Andrés Moreno",
            salario_base=Decimal("2100000"),
            fecha_ingreso=date(2023, 1, 1),
        )

        prima = self.liquidador.calcular_prima_servicios(
            empleado=empleado,
            fecha_inicio=date(2024, 7, 1),
            fecha_fin=date(2024, 12, 31),
        )

        # 184 días (jul-dic tiene 31+31+30+31+30+31)
        dias = 184
        esperado = (Decimal("2100000") * dias) / 360
        self.assertAlmostEqual(float(prima), float(esperado), places=2)

    def test_prima_semestre_parcial(self):
        """Prima para empleado que ingresa a mitad de semestre"""
        empleado = EmpleadoLiquidacion(
            identificacion="1010101010",
            nombre="Mónica Reyes",
            salario_base=Decimal("1400000"),
            fecha_ingreso=date(2024, 3, 15),
        )

        # Solo trabaja marzo 15 a junio 30
        prima = self.liquidador.calcular_prima_servicios(
            empleado=empleado,
            fecha_inicio=date(2024, 3, 15),
            fecha_fin=date(2024, 6, 30),
        )

        # 107 días aproximadamente
        dias = 107
        esperado = (Decimal("1400000") * dias) / 360
        self.assertAlmostEqual(float(prima), float(esperado), places=2)

    def test_prima_salario_integral_no_aplica(self):
        """Salario integral no recibe prima separada"""
        empleado = EmpleadoLiquidacion(
            identificacion="1212121212",
            nombre="Fernando Silva",
            salario_base=Decimal("18000000"),
            fecha_ingreso=date(2023, 1, 1),
            es_salario_integral=True,
        )

        prima = self.liquidador.calcular_prima_servicios(
            empleado=empleado,
            fecha_inicio=date(2024, 1, 1),
            fecha_fin=date(2024, 6, 30),
        )

        self.assertEqual(prima, Decimal("0"))


class TestVacaciones(unittest.TestCase):
    """Tests para cálculo de vacaciones"""

    def setUp(self):
        self.liquidador = LiquidacionPrestaciones()

    def test_vacaciones_ano_completo(self):
        """Vacaciones causadas tras un año completo"""
        empleado = EmpleadoLiquidacion(
            identificacion="1313131313",
            nombre="Gloria Jiménez",
            salario_base=Decimal("1700000"),
            fecha_ingreso=date(2023, 1, 1),
        )

        vacaciones = self.liquidador.calcular_vacaciones(
            empleado=empleado,
            dias_causados=15,  # 15 días hábiles por año
        )

        # Vacaciones = (salario / 30) * días causados
        esperado = (Decimal("1700000") / 30) * 15
        self.assertEqual(vacaciones, esperado.quantize(Decimal("0.01")))

    def test_vacaciones_proporcionales(self):
        """Vacaciones proporcionales por tiempo trabajado"""
        empleado = EmpleadoLiquidacion(
            identificacion="1414141414",
            nombre="Héctor Ospina",
            salario_base=Decimal("2000000"),
            fecha_ingreso=date(2023, 7, 1),
        )

        # 6 meses trabajados = 7.5 días de vacaciones
        dias_causados = Decimal("7.5")
        vacaciones = self.liquidador.calcular_vacaciones(
            empleado=empleado,
            dias_causados=dias_causados,
        )

        esperado = (Decimal("2000000") / 30) * dias_causados
        self.assertEqual(vacaciones, esperado.quantize(Decimal("0.01")))

    def test_vacaciones_compensadas_liquidacion(self):
        """Vacaciones compensadas en dinero en liquidación final"""
        empleado = EmpleadoLiquidacion(
            identificacion="1515151515",
            nombre="Isabel Mendoza",
            salario_base=Decimal("2300000"),
            fecha_ingreso=date(2022, 1, 1),
        )

        # Empleado tiene 15 días pendientes de vacaciones
        dias_pendientes = 15
        compensacion = self.liquidador.calcular_vacaciones(
            empleado=empleado,
            dias_causados=dias_pendientes,
        )

        esperado = (Decimal("2300000") / 30) * dias_pendientes
        self.assertEqual(compensacion, esperado.quantize(Decimal("0.01")))

    def test_vacaciones_salario_integral(self):
        """Empleado salario integral también causa vacaciones"""
        empleado = EmpleadoLiquidacion(
            identificacion="1616161616",
            nombre="Jaime Parra",
            salario_base=Decimal("20000000"),
            fecha_ingreso=date(2023, 1, 1),
            es_salario_integral=True,
        )

        # Salario integral SÍ causa vacaciones (no están incluidas)
        dias_causados = 15
        vacaciones = self.liquidador.calcular_vacaciones(
            empleado=empleado,
            dias_causados=dias_causados,
        )

        # Base para vacaciones es el 70% del salario integral
        base_salario = Decimal("20000000") * Decimal("0.70")
        esperado = (base_salario / 30) * dias_causados
        self.assertEqual(vacaciones, esperado.quantize(Decimal("0.01")))


class TestLiquidacionFinal(unittest.TestCase):
    """Tests para liquidación final de contrato"""

    def setUp(self):
        self.liquidador = LiquidacionPrestaciones()

    def test_liquidacion_final_completa(self):
        """Liquidación final con todos los conceptos"""
        empleado = EmpleadoLiquidacion(
            identificacion="1717171717",
            nombre="Karen Sánchez",
            salario_base=Decimal("2500000"),
            fecha_ingreso=date(2023, 1, 1),
        )

        liquidacion = self.liquidador.calcular_liquidacion_final(
            empleado=empleado,
            fecha_retiro=date(2024, 6, 30),
            dias_vacaciones_pendientes=15,
        )

        # Debe incluir: cesantías acumuladas, intereses cesantías,
        # prima proporcional, vacaciones compensadas
        self.assertIn("cesantias", liquidacion)
        self.assertIn("intereses_cesantias", liquidacion)
        self.assertIn("prima_servicios", liquidacion)
        self.assertIn("vacaciones", liquidacion)
        self.assertIn("total", liquidacion)

        # Total debe ser suma de todos los conceptos
        total_calculado = sum(
            liquidacion[k]
            for k in liquidacion
            if k != "total" and isinstance(liquidacion[k], Decimal)
        )
        self.assertEqual(liquidacion["total"], total_calculado)

    def test_liquidacion_con_salario_pendiente(self):
        """Liquidación incluye días trabajados del mes"""
        empleado = EmpleadoLiquidacion(
            identificacion="1818181818",
            nombre="Luis Torres",
            salario_base=Decimal("1900000"),
            fecha_ingreso=date(2023, 6, 1),
        )

        # Retira el día 15 del mes
        liquidacion = self.liquidador.calcular_liquidacion_final(
            empleado=empleado,
            fecha_retiro=date(2024, 6, 15),
            dias_trabajados_mes=15,
        )

        self.assertIn("salario_mes", liquidacion)

        # Salario proporcional = (salario / 30) * días trabajados
        esperado = (Decimal("1900000") / 30) * 15
        self.assertEqual(
            liquidacion["salario_mes"], esperado.quantize(Decimal("0.01"))
        )

    def test_liquidacion_con_deducciones(self):
        """Liquidación puede tener deducciones (préstamos, anticipos)"""
        empleado = EmpleadoLiquidacion(
            identificacion="1919191919",
            nombre="Mariana Rojas",
            salario_base=Decimal("2200000"),
            fecha_ingreso=date(2023, 1, 1),
        )

        deducciones = {
            "prestamo_empresa": Decimal("500000"),
            "anticipo": Decimal("200000"),
        }

        liquidacion = self.liquidador.calcular_liquidacion_final(
            empleado=empleado,
            fecha_retiro=date(2024, 3, 31),
            deducciones=deducciones,
        )

        self.assertIn("deducciones", liquidacion)
        self.assertEqual(
            liquidacion["deducciones"]["prestamo_empresa"], Decimal("500000")
        )

        # Neto = total devengado - deducciones
        total_deducciones = sum(deducciones.values())
        neto_esperado = liquidacion["total"] - total_deducciones
        self.assertEqual(liquidacion["neto_pagar"], neto_esperado)


class TestInteresesCesantias(unittest.TestCase):
    """Tests para cálculo de intereses sobre cesantías"""

    def setUp(self):
        self.liquidador = LiquidacionPrestaciones()

    def test_intereses_cesantias_ano_completo(self):
        """Intereses del 12% anual sobre cesantías"""
        cesantias_acumuladas = Decimal("1500000")

        intereses = self.liquidador.calcular_intereses_cesantias(
            cesantias_acumuladas=cesantias_acumuladas,
            dias_trabajados=360,  # Año completo
        )

        # 12% anual
        esperado = cesantias_acumuladas * Decimal("0.12")
        self.assertEqual(intereses, esperado.quantize(Decimal("0.01")))

    def test_intereses_cesantias_proporcional(self):
        """Intereses proporcionales por periodo menor a año"""
        cesantias_acumuladas = Decimal("800000")

        # 180 días = medio año
        intereses = self.liquidador.calcular_intereses_cesantias(
            cesantias_acumuladas=cesantias_acumuladas,
            dias_trabajados=180,
        )

        # 6% (mitad del 12% anual)
        esperado = cesantias_acumuladas * Decimal("0.06")
        self.assertEqual(intereses, esperado.quantize(Decimal("0.01")))

    def test_intereses_cesantias_mes(self):
        """Intereses mensuales sobre cesantías"""
        cesantias_acumuladas = Decimal("1200000")

        # 30 días
        intereses = self.liquidador.calcular_intereses_cesantias(
            cesantias_acumuladas=cesantias_acumuladas,
            dias_trabajados=30,
        )

        # 1% mensual (12% / 12)
        esperado = cesantias_acumuladas * Decimal("0.01")
        self.assertEqual(intereses, esperado.quantize(Decimal("0.01")))


class TestCasosEspeciales(unittest.TestCase):
    """Tests para casos especiales y edge cases"""

    def setUp(self):
        self.liquidador = LiquidacionPrestaciones()

    def test_empleado_menos_mes(self):
        """Empleado que trabaja menos de un mes"""
        empleado = EmpleadoLiquidacion(
            identificacion="2020202020",
            nombre="Natalia Cruz",
            salario_base=Decimal("1300000"),
            fecha_ingreso=date(2024, 6, 20),
        )

        liquidacion = self.liquidador.calcular_liquidacion_final(
            empleado=empleado,
            fecha_retiro=date(2024, 6, 28),
            dias_trabajados_mes=8,
        )

        # Debe calcular proporcional de todos los conceptos
        self.assertGreater(liquidacion["salario_mes"], Decimal("0"))
        self.assertGreater(liquidacion["cesantias"], Decimal("0"))

    def test_incapacidad_no_descuenta_prestaciones(self):
        """Días de incapacidad no afectan prestaciones sociales"""
        empleado = EmpleadoLiquidacion(
            identificacion="2121212121",
            nombre="Oscar Ramírez",
            salario_base=Decimal("2000000"),
            fecha_ingreso=date(2024, 1, 1),
        )

        # Empleado tuvo 15 días de incapacidad en el mes
        prima = self.liquidador.calcular_prima_servicios(
            empleado=empleado,
            fecha_inicio=date(2024, 1, 1),
            fecha_fin=date(2024, 6, 30),
            dias_incapacidad=15,
        )

        # Prima se calcula sobre 180 días completos (incapacidad no descuenta)
        esperado = (Decimal("2000000") * 180) / 360
        self.assertEqual(prima, esperado.quantize(Decimal("0.01")))

    def test_licencia_no_remunerada_descuenta(self):
        """Licencia no remunerada sí descuenta de prestaciones"""
        empleado = EmpleadoLiquidacion(
            identificacion="2222222222",
            nombre="Paula Gutiérrez",
            salario_base=Decimal("1800000"),
            fecha_ingreso=date(2024, 1, 1),
        )

        # Empleado tuvo 30 días de licencia no remunerada
        cesantias = self.liquidador.calcular_cesantias_anuales(
            empleado=empleado,
            fecha_inicio=date(2024, 1, 1),
            fecha_fin=date(2024, 12, 31),
            dias_no_remunerados=30,
        )

        # Se calculan sobre 330 días en lugar de 360
        dias_efectivos = 360 - 30
        esperado = (Decimal("1800000") * dias_efectivos) / 360
        self.assertEqual(cesantias, esperado.quantize(Decimal("0.01")))

    def test_variacion_salarial_promedia(self):
        """Variaciones salariales en el año promedian para cesantías"""
        empleado = EmpleadoLiquidacion(
            identificacion="2323232323",
            nombre="Ricardo Álvarez",
            salario_base=Decimal("3000000"),
            fecha_ingreso=date(2023, 1, 1),
        )

        # Historial: 6 meses a 2.5M, 6 meses a 3M
        salarios_mensuales = [Decimal("2500000")] * 6 + [Decimal("3000000")] * 6
        promedio = sum(salarios_mensuales) / 12

        cesantias = self.liquidador.calcular_cesantias_anuales(
            empleado=empleado,
            fecha_inicio=date(2023, 1, 1),
            fecha_fin=date(2023, 12, 31),
            salario_promedio=promedio,
        )

        esperado = promedio  # Año completo
        self.assertEqual(cesantias, esperado)

    def test_auxilio_transporte_salario_alto_no_aplica(self):
        """Auxilio de transporte no aplica si salario > 2 SMMLV"""
        empleado = EmpleadoLiquidacion(
            identificacion="2424242424",
            nombre="Sofía Medina",
            salario_base=Decimal("2800000"),  # Mayor a 2 * 1.300.000
            fecha_ingreso=date(2024, 1, 1),
        )

        # No se incluye auxilio transporte en la base
        cesantias = self.liquidador.calcular_cesantias_mes(
            empleado=empleado,
            fecha_corte=date(2024, 1, 31),
        )

        base = Decimal("2800000")  # Solo salario base
        esperado = (base * 30) / 360
        self.assertEqual(cesantias, esperado.quantize(Decimal("0.01")))

    def test_horas_extras_promedio_ultimos_6_meses(self):
        """Horas extras se promedian últimos 6 meses para base prestaciones"""
        empleado = EmpleadoLiquidacion(
            identificacion="2525252525",
            nombre="Tomás Bernal",
            salario_base=Decimal("1500000"),
            fecha_ingreso=date(2023, 1, 1),
        )

        # Historial de horas extras últimos 6 meses
        horas_extras_mes = [
            Decimal("200000"),
            Decimal("250000"),
            Decimal("180000"),
            Decimal("300000"),
            Decimal("220000"),
            Decimal("240000"),
        ]
        promedio_horas = sum(horas_extras_mes) / 6

        conceptos = [
            ConceptoDevengado(
                tipo=TipoConcepto.HORA_EXTRA,
                valor=promedio_horas,
            )
        ]

        cesantias = self.liquidador.calcular_cesantias_mes(
            empleado=empleado,
            fecha_corte=date(2024, 1, 31),
            conceptos_adicionales=conceptos,
        )

        base = Decimal("1500000") + promedio_horas
        esperado = (base * 30) / 360
        self.assertEqual(cesantias, esperado.quantize(Decimal("0.01")))


class TestValidaciones(unittest.TestCase):
    """Tests para validaciones y manejo de errores"""

    def setUp(self):
        self.liquidador = LiquidacionPrestaciones()

    def test_fecha_retiro_anterior_ingreso(self):
        """Error si fecha de retiro es anterior a ingreso"""
        empleado = EmpleadoLiquidacion(
            identificacion="2626262626",
            nombre="Valentina Ortiz",
            salario_base=Decimal("1600000"),
            fecha_ingreso=date(2024, 1, 1),
        )

        with self.assertR