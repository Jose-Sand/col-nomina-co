"""
Módulo de liquidación de prestaciones sociales según Código Sustantivo del Trabajo colombiano.

Calcula cesantías, intereses sobre cesantías, prima de servicios, vacaciones y demás
conceptos según normativa vigente. Maneja salario ordinario y salario integral.
"""

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Optional, List, Dict
from dateutil.relativedelta import relativedelta


class TipoSalario(Enum):
    """Tipo de salario del empleado según normativa colombiana."""
    ORDINARIO = "ordinario"  # Salario hasta 13 SMMLV
    INTEGRAL = "integral"    # Salario mayor a 13 SMMLV (incluye prestaciones)


@dataclass
class ConceptoSalarial:
    """
    Representa un concepto que puede ser factor salarial o no salarial.
    
    Importante: No todos los pagos son factor salarial. Por ejemplo:
    - Bonificaciones ocasionales: NO salarial
    - Auxilio de transporte: NO salarial (pero obligatorio < 2 SMMLV)
    - Horas extras, recargos: SÍ salarial
    """
    nombre: str
    valor: Decimal
    es_salarial: bool = True
    descripcion: str = ""


@dataclass
class PeriodoLiquidacion:
    """
    Período para liquidar prestaciones sociales.
    
    La ley colombiana exige cortes específicos:
    - Cesantías: 31 de diciembre de cada año
    - Prima: 30 de junio y 20 de diciembre
    - Vacaciones: Al cumplir año de servicio
    """
    fecha_inicio: date
    fecha_fin: date
    dias_trabajados: Optional[int] = None
    
    def __post_init__(self):
        """Calcula días trabajados si no se especificaron."""
        if self.dias_trabajados is None:
            self.dias_trabajados = (self.fecha_fin - self.fecha_inicio).days + 1
    
    def get_dias_para_cesantias(self) -> int:
        """
        Retorna días para cálculo de cesantías.
        Cesantías se calculan por días calendario trabajados.
        """
        return self.dias_trabajados
    
    def get_dias_para_prima(self) -> int:
        """
        Retorna días para cálculo de prima de servicios.
        Prima se calcula por semestre (180 días máximo).
        """
        return min(self.dias_trabajados, 180)
    
    def get_dias_para_vacaciones(self) -> Decimal:
        """
        Retorna días laborados para cálculo de vacaciones.
        Se acumulan 15 días hábiles por año trabajado.
        Proporción: 1.25 días por mes (15/12).
        """
        return Decimal(self.dias_trabajados) / Decimal("30")


@dataclass
class Empleado:
    """
    Información del empleado necesaria para liquidación.
    
    Campos requeridos por normativa:
    - tipo_identificacion y numero_identificacion: Para reportes PILA
    - fecha_ingreso: Base para todos los cálculos temporales
    - salario_base: Salario mensual contractual
    """
    tipo_identificacion: str  # CC, CE, PA, NIT
    numero_identificacion: str
    nombres: str
    apellidos: str
    fecha_ingreso: date
    salario_base: Decimal
    tipo_salario: TipoSalario = TipoSalario.ORDINARIO
    auxilio_transporte: Decimal = Decimal("0")
    otros_conceptos: List[ConceptoSalarial] = field(default_factory=list)
    
    def get_salario_base_diario(self) -> Decimal:
        """
        Calcula salario base diario.
        Dividido por 30 según convención legal colombiana.
        """
        return (self.salario_base / Decimal("30")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
    
    def es_salario_integral(self, smmlv: Decimal) -> bool:
        """
        Determina si aplica salario integral.
        Requisito: Salario base >= 13 SMMLV (Art 132 CST).
        """
        if self.tipo_salario == TipoSalario.INTEGRAL:
            return True
        return self.salario_base >= (smmlv * Decimal("13"))


@dataclass
class BasesSalariales:
    """
    Bases salariales para liquidación de prestaciones.
    
    La base incluye:
    - Salario base
    - Horas extras
    - Recargos nocturnos, dominicales
    - Comisiones regulares
    - Bonificaciones habituales
    
    NO incluye pagos no constitutivos de salario.
    """
    salario_base: Decimal
    promedio_extras: Decimal = Decimal("0")
    promedio_comisiones: Decimal = Decimal("0")
    otros_salariales: Decimal = Decimal("0")
    
    def get_base_total(self) -> Decimal:
        """Base total para cálculo de prestaciones."""
        return (
            self.salario_base +
            self.promedio_extras +
            self.promedio_comisiones +
            self.otros_salariales
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    
    def get_base_diaria(self) -> Decimal:
        """Base diaria para cesantías y prima."""
        return (self.get_base_total() / Decimal("30")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )


@dataclass
class ResultadoCesantias:
    """
    Resultado del cálculo de cesantías.
    
    Fórmula legal (Art 249 CST):
    Cesantías = (Salario base mensual * Días trabajados) / 360
    
    Para salario variable se toma promedio del último año.
    """
    valor_cesantias: Decimal
    valor_intereses: Decimal  # 12% anual sobre cesantías (Art 99 Ley 50/1990)
    dias_liquidados: int
    base_calculo: Decimal
    fecha_corte: date
    observaciones: str = ""


@dataclass
class ResultadoPrima:
    """
    Resultado del cálculo de prima de servicios.
    
    Fórmula legal (Art 306 CST):
    Prima = (Salario base mensual * Días trabajados) / 360
    
    Se paga en dos cuotas:
    - 50% antes del 30 de junio
    - 50% en primeros 20 días de diciembre
    """
    valor_prima: Decimal
    dias_liquidados: int
    base_calculo: Decimal
    periodo_inicio: date
    periodo_fin: date
    semestre: int  # 1 o 2
    observaciones: str = ""


@dataclass
class ResultadoVacaciones:
    """
    Resultado del cálculo de vacaciones.
    
    Normativa (Art 186 CST):
    - 15 días hábiles de descanso remunerado por año trabajado
    - Proporcional: 1.25 días por mes
    - Base: Salario ordinario (sin extras ni recargos)
    
    Compensación en dinero solo permitida en liquidación final.
    """
    dias_causados: Decimal  # Días hábiles acumulados
    valor_vacaciones: Decimal  # Si se compensan en dinero
    base_calculo: Decimal
    periodo_inicio: date
    periodo_fin: date
    observaciones: str = ""


@dataclass
class LiquidacionPrestaciones:
    """
    Consolidado de liquidación de prestaciones sociales.
    
    Incluye todos los conceptos obligatorios por ley para un período dado.
    """
    empleado: Empleado
    periodo: PeriodoLiquidacion
    cesantias: ResultadoCesantias
    prima: ResultadoPrima
    vacaciones: ResultadoVacaciones
    fecha_liquidacion: date
    
    def get_total_prestaciones(self) -> Decimal:
        """Total de prestaciones sociales liquidadas."""
        return (
            self.cesantias.valor_cesantias +
            self.cesantias.valor_intereses +
            self.prima.valor_prima +
            self.vacaciones.valor_vacaciones
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class CalculadoraPrestaciones:
    """
    Motor de cálculo de prestaciones sociales según normativa colombiana.
    
    Implementa las fórmulas del Código Sustantivo del Trabajo y jurisprudencia
    de la Corte Constitucional sobre interpretación de normas laborales.
    """
    
    def __init__(self, smmlv: Decimal, auxilio_transporte: Decimal):
        """
        Inicializa calculadora con valores legales vigentes.
        
        Args:
            smmlv: Salario Mínimo Mensual Legal Vigente
            auxilio_transporte: Auxilio de transporte legal (si salario < 2 SMMLV)
        """
        self.smmlv = smmlv
        self.auxilio_transporte_legal = auxilio_transporte
        self.tasa_interes_cesantias = Decimal("0.12")  # 12% anual
    
    def calcular_base_salarial(
        self,
        empleado: Empleado,
        fecha_inicio: date,
        fecha_fin: date
    ) -> BasesSalariales:
        """
        Calcula la base salarial promedio para liquidar prestaciones.
        
        Para salario fijo: se toma el salario base del período.
        Para salario variable: promedio de los últimos 12 meses o del período trabajado.
        
        Args:
            empleado: Datos del empleado
            fecha_inicio: Inicio del período a promediar
            fecha_fin: Fin del período a promediar
            
        Returns:
            Bases salariales calculadas
        """
        # Para salario integral, el 70% es factor salarial
        if empleado.es_salario_integral(self.smmlv):
            factor_salarial = empleado.salario_base * Decimal("0.70")
        else:
            factor_salarial = empleado.salario_base
        
        # Suma otros conceptos salariales
        otros_salariales = sum(
            concepto.valor 
            for concepto in empleado.otros_conceptos 
            if concepto.es_salarial
        )
        
        return BasesSalariales(
            salario_base=factor_salarial,
            otros_salariales=otros_salariales
        )
    
    def calcular_cesantias(
        self,
        empleado: Empleado,
        periodo: PeriodoLiquidacion,
        bases: Optional[BasesSalariales] = None
    ) -> ResultadoCesantias:
        """
        Calcula cesantías según Art 249 CST.
        
        Fórmula:
        Cesantías = (Salario mensual promedio * Días trabajados) / 360
        
        El auxilio de transporte NO es base para cesantías (solo para empleados
        con salario < 2 SMMLV, pero no suma a la base de cálculo).
        
        Args:
            empleado: Datos del empleado
            periodo: Período a liquidar
            bases: Bases salariales (si no se proveen, se calculan)
            
        Returns:
            Resultado con cesantías e intereses
        """
        if bases is None:
            bases = self.calcular_base_salarial(
                empleado,
                periodo.fecha_inicio,
                periodo.fecha_fin
            )
        
        # Salario integral no causa cesantías separadas (ya están incluidas)
        if empleado.es_salario_integral(self.smmlv):
            return ResultadoCesantias(
                valor_cesantias=Decimal("0"),
                valor_intereses=Decimal("0"),
                dias_liquidados=periodo.get_dias_para_cesantias(),
                base_calculo=bases.get_base_total(),
                fecha_corte=periodo.fecha_fin,
                observaciones="Salario integral incluye prestaciones sociales"
            )
        
        # Cálculo cesantías: (Base mensual * Días) / 360
        dias = periodo.get_dias_para_cesantias()
        base_mensual = bases.get_base_total()
        
        valor_cesantias = (
            (base_mensual * Decimal(dias)) / Decimal("360")
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        
        # Intereses sobre cesantías: 12% anual
        # Se calculan sobre el saldo acumulado al 31 de diciembre
        # Para períodos inferiores a un año: proporcional
        dias_interes = (periodo.fecha_fin - periodo.fecha_inicio).days
        tasa_proporcional = self.tasa_interes_cesantias * (
            Decimal(dias_interes) / Decimal("360")
        )
        
        valor_intereses = (
            valor_cesantias * tasa_proporcional
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        
        return ResultadoCesantias(
            valor_cesantias=valor_cesantias,
            valor_intereses=valor_intereses,
            dias_liquidados=dias,
            base_calculo=base_mensual,
            fecha_corte=periodo.fecha_fin
        )
    
    def calcular_prima(
        self,
        empleado: Empleado,
        periodo: PeriodoLiquidacion,
        semestre: int,
        bases: Optional[BasesSalariales] = None
    ) -> ResultadoPrima:
        """
        Calcula prima de servicios según Art 306 CST.
        
        Fórmula:
        Prima = (Salario mensual promedio * Días trabajados) / 360
        
        La prima se liquida por semestre:
        - Primer semestre: 1 enero - 30 junio
        - Segundo semestre: 1 julio - 31 diciembre
        
        Args:
            empleado: Datos del empleado
            periodo: Período a liquidar (máximo 180 días)
            semestre: 1 o 2
            bases: Bases salariales (si no se proveen, se calculan)
            
        Returns:
            Resultado de prima de servicios
        """
        if semestre not in [1, 2]:
            raise ValueError("Semestre debe ser 1 o 2")
        
        if bases is None:
            bases = self.calcular_base_salarial(
                empleado,
                periodo.fecha_inicio,
                periodo.fecha_fin
            )
        
        # Salario integral no causa prima separada
        if empleado.es_salario_integral(self.smmlv):
            return ResultadoPrima(
                valor_prima=Decimal("0"),
                dias_liquidados=periodo.get_dias_para_prima(),
                base_calculo=bases.get_base_total(),
                periodo_inicio=periodo.fecha_inicio,
                periodo_fin=periodo.fecha_fin,
                semestre=semestre,
                observaciones="Salario integral incluye prestaciones sociales"
            )
        
        # Cálculo prima: (Base mensual * Días) / 360
        dias = periodo.get_dias_para_prima()
        base_mensual = bases.get_base_total()
        
        valor_prima = (
            (base_mensual * Decimal(dias)) / Decimal("360")
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        
        return ResultadoPrima(
            valor_prima=valor_prima,
            dias_liquidados=dias,
            base_calculo=base_mensual,
            periodo_inicio=periodo.fecha_inicio,
            periodo_fin=periodo.fecha_fin,
            semestre=semestre
        )
    
    def calcular_vacaciones(
        self,
        empleado: Empleado,
        periodo: PeriodoLiquidacion,
        bases: Optional[BasesSalariales] = None,
        compensar_en_dinero: bool = False
    ) -> ResultadoVacaciones:
        """
        Calcula vacaciones según Art 186 CST.
        
        Regla: 15 días hábiles de vacaciones remuneradas por cada año de servicio.
        Proporcional: 1.25 días por mes trabajado.
        
        Base de cálculo: Salario ordinario (NO incluye horas extras, comisiones variables).
        
        Las vacaciones solo se compensan en dinero cuando:
        1. Terminación del contrato
        2. Autorización expresa del Ministerio del Trabajo (casos excepcionales)
        
        Args:
            empleado: Datos del empleado
            periodo: Período trabajado
            bases: Bases salariales
            compensar_en_dinero: Si se liquidan en dinero (solo en retiro)
            
        Returns:
            Resultado de vacaciones causadas
        """
        if bases is None:
            bases = self.calcular_base_salarial(
                empleado,
                periodo.fecha_inicio,
                periodo.fecha_fin
            )
        
        # Días de vacaciones causados (1.25 días por mes, basado en días trabajados)
        meses_trabajados = periodo.get_dias_para_vacaciones()
        dias_causados = (meses_trabajados * Decimal("1.25")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        
        # Base: solo salario ordinario (sin extras)
        base_mensual = bases.salario_base
        base_diaria = base_mensual / Decimal("30")
        
        # Valor en dinero (si se compensan)
        if compensar_en_dinero:
            valor_vacaciones = (base_diaria * dias_causados).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            obs = "Compensación en dinero autorizada"
        else:
            valor_vacaciones = Decimal("0")
            obs = "Días causados pendientes de disfrutar"
        
        return ResultadoVacaciones(
            dias_causados=dias_causados,
            valor_vacaciones=valor_vacaciones,
            base_calculo=base_mensual,
            periodo_inicio=periodo.fecha_inicio,
            periodo_fin=periodo.fecha_fin,
            observaciones=obs
        )
    
    def liquidar_prestaciones(
        self,
        empleado: Empleado,
        fecha_corte: date,
        liquidar_vacaciones_dinero: bool = False
    ) -> LiquidacionPrestaciones:
        """
        Liquida todas las prestaciones sociales para una fecha de corte.
        
        Típicamente usado para:
        - Liquidación anual (31 de diciembre)
        - Liquidación final (terminación contrato)
        - Cálculos intermedios (auditoría, proyecciones)
        
        Args:
            empleado: Datos del empleado
            fecha_corte: Fecha hasta la cual liquidar
            liquidar_vacaciones_dinero: Si se compensan vacaciones (solo en retiro)
            
        Returns:
            Liquidación completa de prestaciones
        """
        # Período desde ingreso hasta fecha de corte
        periodo_completo = PeriodoLiquidacion(
            fecha_inicio=empleado.fecha_ingreso,
            fecha_fin=fecha_corte
        )
        
        # Calcular bases salariales
        bases = self.calcular_base_salarial(
            empleado,
            periodo_completo.fecha_inicio,
            periodo_completo.fecha_fin
        )
        
        # Calcular cesantías
        cesantias = self.calcular_cesantias(empleado, periodo_completo, bases)
        
        # Determinar semestre para prima
        semestre = 1 if fecha_corte.month <= 6 else 2
        
        # Período de prima (semestral)
        if semestre == 1:
            inicio_semestre = date(fecha_corte.year, 1, 1)
        else:
            inicio_semestre = date(fecha_corte.year, 7, 1)
        
        periodo_prima = PeriodoLiquidacion(
            fecha_inicio=max(inicio_semestre, empleado.fecha_ingreso),
            fecha_fin=fecha_corte
        )
        
        prima = self.calcular_prima(empleado, periodo_prima, semestre, bases)
        
        # Calcular vacaciones
        vacaciones = self.calcular_vacaciones(
            empleado,
            periodo_completo,
            bases,
            compensar_en_dinero=liquidar_vacaciones_dinero
        )
        
        return LiquidacionPrestaciones(
            empleado=empleado,
            periodo=periodo_completo,
            cesantias=cesantias,
            prima=prima,
            vacaciones=vacaciones,
            fecha_liquidacion=datetime.now().date()
        )
    
    def liquidar_final(
        self,
        empleado: Empleado,
        fecha_retiro: date,
        ultimo_pago_cesantias: Optional[date] = None,
        ultimo_pago_prima: Optional[date] = None
    ) -> LiquidacionPrestaciones:
        """
        Liquida prestaciones en terminación de contrato.
        
        Debe incluir:
        - Cesantías desde último pago hasta fecha de retiro
        - Intereses sobre cesantías
        - Prima proporcional del semestre
        - Vacaciones causadas y no disfrutadas (compensadas en dinero)
        
        Args:
            empleado: Datos del empleado
            fecha_retiro: Fecha de terminación del contrato
            ultimo_pago_cesantias: Fecha del último pago (default: 31 dic año anterior)
            ultimo_pago_prima: Fecha del último pago de prima
            
        Returns:
            Liquidación final completa
        """
        # Si no hay fecha de último pago de cesantías, asumir 31 dic año anterior
        if ultimo_pago_cesantias is None:
            if fecha_retiro.month == 1 and fecha_retiro.day == 1:
                ultimo_pago_cesantias = date(fecha_retiro.year - 1, 12, 31)
            else:
                ultimo_pago_cesantias = date(fecha_retiro.year - 1, 12, 31)
            
            # Si es primer año, desde fecha de ingreso
            if ultimo_pago_cesantias < empleado.fecha_ingreso:
                ultimo_pago_cesantias = empleado.fecha_ingreso
        
        # Período de cesantías a liquidar
        periodo_cesantias = PeriodoLiquidacion(
            fecha_inicio=ultimo_pago_cesantias + timedelta(days=1),
            fecha_fin=fecha_retiro
        )
        
        # Período de prima (desde inicio de semestre)
        if fecha_retiro.month <= 6:
            inicio_prima = date(fecha_retiro.year, 1, 1)
        else:
            inicio_prima = date(fecha_retiro.year, 7, 1)
        
        periodo_prima = PeriodoLiquidacion(
            fecha_inicio=max(inicio_prima, empleado.fecha_ingreso),
            fecha_fin=fecha_retiro
        )
        
        # Bases salariales
        bases = self.calcular_base_salarial(
            empleado,
            fecha_retiro - timedelta(days=360),  # Promedio último año
            fecha_retiro
        )
        
        # Calcular cada concepto
        cesantias = self.calcular_cesantias(empleado, periodo_cesantias, bases)
        
        semestre = 1 if fecha_retiro.month <= 6 else 2
        prima = self.calcular_prima(empleado, periodo_prima, semestre, bases)
        
        # Vacaciones: desde último disfrute (simplificado: desde ingreso)
        periodo_vacaciones = PeriodoLiquidacion(
            fecha_inicio=empleado.fecha_ingreso,
            fecha_fin=fecha_retiro
        )
        
        vacaciones = self.calcular_vacaciones(
            empleado,
            periodo_vacaciones,
            bases,
            compensar_en_dinero=True  # Siempre se compensan en liquidación final
        )
        
        return LiquidacionPrestaciones(
            empleado=empleado,
            periodo=periodo_cesantias,
            cesantias=cesantias,
            prima=prima,
            vacaciones=vacaciones,
            fecha_liquidacion=datetime.now().date()
        )


def crear_periodo_semestre(year: int, semestre: int) -> PeriodoLiquidacion:
    """
    Crea un período de liquidación para un semestre específico.
    
    Args:
        year: Año
        semestre: 1 (ene-jun) o 2 (jul-dic)
        
    Returns:
        Período de liquidación semestral
    """
    if semestre == 1:
        return PeriodoLiquidacion(
            fecha_inicio=date(year, 1, 1),
            fecha_fin=date(year, 6, 30)
        )
    else:
        return PeriodoLiquidacion(
            fecha_inicio=date(year, 7, 1),
            fecha_fin=date(year, 12, 31)
        )


def crear_periodo_anual(year: int) -> PeriodoLiquidacion:
    """
    Crea un período de liquidación anual para cesantías.
    
    Args:
        year: Año a liquidar
        
    Returns:
        Período de liquidación anual (1 ene - 31 dic)
    """
    return PeriodoLiquidacion(
        fecha_inicio=date(year, 1, 1),
        fecha_fin=date(year, 12, 31)
    )