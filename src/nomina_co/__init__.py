"""
nomina-co: Librería para cálculo de nómina colombiana y generación XML DIAN

Calcula prestaciones sociales (cesantías, prima, vacaciones), aportes a seguridad social (PILA),
retención en la fuente según tabla UVT vigente y genera XML de nómina electrónica conforme
a la resolución 000013 de la DIAN.

Uso básico:
    >>> from nomina_co import EmpleadoConfig, Nomina, calcular_nomina
    >>> empleado = EmpleadoConfig(
    ...     identificacion="1234567890",
    ...     tipo_identificacion="CC",
    ...     nombre="Juan Pérez",
    ...     salario_basico=2500000,
    ...     tipo_contrato="TERMINO_INDEFINIDO"
    ... )
    >>> nomina = Nomina(empleado=empleado, periodo="2024-01")
    >>> resultado = calcular_nomina(nomina)
    >>> print(f"Neto a pagar: ${resultado.total_devengado - resultado.total_deducciones:,.0f}")

Características principales:
- Cálculo automático de prestaciones sociales según código sustantivo del trabajo
- Aportes PILA (salud 12.5%, pensión 16%, ARL según nivel de riesgo)
- Retención en la fuente con tabla UVT 2024 actualizada
- Soporte para salario integral, horas extras diurnas/nocturnas, dominicales, festivos
- Manejo de incapacidades y licencias con descuentos correctos
- Generación de XML nómina electrónica DIAN resolución 000013
- Liquidación final con indemnizaciones y conceptos legales
"""

from decimal import Decimal
from typing import Optional, Dict, Any, List
from datetime import date, datetime
from enum import Enum

# Versión del paquete
__version__ = "0.1.0"

# Constantes legales colombianas actualizadas 2024
SALARIO_MINIMO_2024 = Decimal("1300000")
AUXILIO_TRANSPORTE_2024 = Decimal("162000")
UVT_2024 = Decimal("47065")  # Unidad de Valor Tributario 2024

# Porcentajes aportes seguridad social
PORCENTAJE_SALUD_EMPLEADO = Decimal("0.04")  # 4% empleado
PORCENTAJE_SALUD_EMPLEADOR = Decimal("0.085")  # 8.5% empleador
PORCENTAJE_PENSION_EMPLEADO = Decimal("0.04")  # 4% empleado
PORCENTAJE_PENSION_EMPLEADOR = Decimal("0.12")  # 12% empleador

# Topes legales
TOPE_SALARIO_INTEGRAL = SALARIO_MINIMO_2024 * Decimal("10")  # 10 SMMLV
TOPE_AUXILIO_TRANSPORTE = SALARIO_MINIMO_2024 * Decimal("2")  # 2 SMMLV


class TipoIdentificacion(str, Enum):
    """Tipos de identificación válidos en Colombia según DIAN"""
    CC = "CC"  # Cédula de ciudadanía
    CE = "CE"  # Cédula de extranjería
    NIT = "NIT"  # Número de identificación tributaria
    TI = "TI"  # Tarjeta de identidad
    PA = "PA"  # Pasaporte
    PEP = "PEP"  # Permiso especial de permanencia


class TipoContrato(str, Enum):
    """Tipos de contrato laboral en Colombia"""
    TERMINO_INDEFINIDO = "TERMINO_INDEFINIDO"
    TERMINO_FIJO = "TERMINO_FIJO"
    OBRA_LABOR = "OBRA_LABOR"
    APRENDIZAJE = "APRENDIZAJE"
    TEMPORAL = "TEMPORAL"


class NivelRiesgoARL(str, Enum):
    """Niveles de riesgo ARL según clasificación colombiana"""
    NIVEL_I = "I"  # Riesgo mínimo: 0.522%
    NIVEL_II = "II"  # Riesgo bajo: 1.044%
    NIVEL_III = "III"  # Riesgo medio: 2.436%
    NIVEL_IV = "IV"  # Riesgo alto: 4.350%
    NIVEL_V = "V"  # Riesgo máximo: 6.960%


class TipoNovedad(str, Enum):
    """Tipos de novedades en nómina"""
    INCAPACIDAD = "INCAPACIDAD"
    LICENCIA = "LICENCIA"
    VACACIONES = "VACACIONES"
    SUSPENSION = "SUSPENSION"
    HORA_EXTRA_DIURNA = "HORA_EXTRA_DIURNA"
    HORA_EXTRA_NOCTURNA = "HORA_EXTRA_NOCTURNA"
    RECARGO_NOCTURNO = "RECARGO_NOCTURNO"
    TRABAJO_DOMINICAL = "TRABAJO_DOMINICAL"


class EmpleadoConfig:
    """
    Configuración del empleado para cálculo de nómina.
    
    Atributos:
        identificacion: Número de identificación (NIT, CC, CE, etc.)
        tipo_identificacion: Tipo de documento (CC, CE, NIT, TI, PA, PEP)
        nombre: Nombre completo del empleado
        salario_basico: Salario básico mensual en pesos colombianos
        tipo_contrato: Tipo de contrato laboral
        fecha_ingreso: Fecha de ingreso del empleado
        salario_integral: Indica si el empleado tiene salario integral
        aplica_auxilio_transporte: Si aplica subsidio de transporte
        nivel_riesgo_arl: Nivel de riesgo para cálculo de ARL
        dependientes: Número de dependientes para retención en la fuente
        porcentaje_fondo_solidaridad: Porcentaje adicional para fondo de solidaridad pensional
    """
    
    def __init__(
        self,
        identificacion: str,
        tipo_identificacion: TipoIdentificacion,
        nombre: str,
        salario_basico: Decimal,
        tipo_contrato: TipoContrato,
        fecha_ingreso: Optional[date] = None,
        salario_integral: bool = False,
        aplica_auxilio_transporte: bool = True,
        nivel_riesgo_arl: NivelRiesgoARL = NivelRiesgoARL.NIVEL_I,
        dependientes: int = 0,
        porcentaje_fondo_solidaridad: Optional[Decimal] = None
    ):
        self.identificacion = identificacion
        self.tipo_identificacion = tipo_identificacion
        self.nombre = nombre
        self.salario_basico = Decimal(str(salario_basico))
        self.tipo_contrato = tipo_contrato
        self.fecha_ingreso = fecha_ingreso or date.today()
        self.salario_integral = salario_integral
        self.nivel_riesgo_arl = nivel_riesgo_arl
        self.dependientes = dependientes
        
        # Determinar si aplica auxilio de transporte
        if salario_integral or salario_basico > TOPE_AUXILIO_TRANSPORTE:
            self.aplica_auxilio_transporte = False
        else:
            self.aplica_auxilio_transporte = aplica_auxilio_transporte
        
        # Calcular porcentaje fondo solidaridad pensional (obligatorio > 4 SMMLV)
        if porcentaje_fondo_solidaridad is not None:
            self.porcentaje_fondo_solidaridad = porcentaje_fondo_solidaridad
        else:
            smmlv_factor = self.salario_basico / SALARIO_MINIMO_2024
            if smmlv_factor >= 16:
                self.porcentaje_fondo_solidaridad = Decimal("0.02")  # 2%
            elif smmlv_factor >= 4:
                self.porcentaje_fondo_solidaridad = Decimal("0.01")  # 1%
            else:
                self.porcentaje_fondo_solidaridad = Decimal("0")


class Nomina:
    """
    Clase principal para representar una nómina de un empleado en un periodo.
    
    Atributos:
        empleado: Configuración del empleado
        periodo: Periodo de nómina en formato YYYY-MM
        dias_trabajados: Días efectivamente trabajados en el periodo (default: 30)
        novedades: Lista de novedades del periodo (horas extras, incapacidades, etc.)
        otros_devengos: Devengos adicionales no salariales
        otros_descuentos: Descuentos adicionales (libranzas, embargos, etc.)
    """
    
    def __init__(
        self,
        empleado: EmpleadoConfig,
        periodo: str,
        dias_trabajados: int = 30,
        novedades: Optional[List[Dict[str, Any]]] = None,
        otros_devengos: Optional[Dict[str, Decimal]] = None,
        otros_descuentos: Optional[Dict[str, Decimal]] = None
    ):
        self.empleado = empleado
        self.periodo = periodo
        self.dias_trabajados = dias_trabajados
        self.novedades = novedades or []
        self.otros_devengos = otros_devengos or {}
        self.otros_descuentos = otros_descuentos or {}
        
        # Validar periodo
        try:
            self.fecha_periodo = datetime.strptime(periodo, "%Y-%m").date()
        except ValueError:
            raise ValueError(f"Periodo inválido '{periodo}'. Use formato YYYY-MM")


class ResultadoNomina:
    """
    Resultado del cálculo de nómina con todos los conceptos desglosados.
    
    Atributos:
        salario_base: Salario básico proporcional a días trabajados
        auxilio_transporte: Subsidio de transporte si aplica
        total_devengado: Total de ingresos del periodo
        salud: Aporte a salud del empleado
        pension: Aporte a pensión del empleado
        fondo_solidaridad: Aporte al fondo de solidaridad pensional
        retencion_fuente: Retención en la fuente
        total_deducciones: Total de descuentos del periodo
        neto_pagar: Valor neto a pagar al empleado
        detalles: Diccionario con conceptos detallados
    """
    
    def __init__(self):
        self.salario_base: Decimal = Decimal("0")
        self.auxilio_transporte: Decimal = Decimal("0")
        self.horas_extras: Decimal = Decimal("0")
        self.recargos: Decimal = Decimal("0")
        self.bonificaciones: Decimal = Decimal("0")
        self.total_devengado: Decimal = Decimal("0")
        
        self.salud: Decimal = Decimal("0")
        self.pension: Decimal = Decimal("0")
        self.fondo_solidaridad: Decimal = Decimal("0")
        self.retencion_fuente: Decimal = Decimal("0")
        self.total_deducciones: Decimal = Decimal("0")
        
        self.neto_pagar: Decimal = Decimal("0")
        self.detalles: Dict[str, Any] = {}


def calcular_nomina(nomina: Nomina) -> ResultadoNomina:
    """
    Calcula la nómina completa de un empleado incluyendo devengos, deducciones y neto a pagar.
    
    Args:
        nomina: Objeto Nomina con configuración del empleado y periodo
        
    Returns:
        ResultadoNomina con todos los conceptos calculados
        
    Raises:
        ValueError: Si los datos de entrada son inválidos
        
    Ejemplo:
        >>> empleado = EmpleadoConfig(
        ...     identificacion="123456789",
        ...     tipo_identificacion=TipoIdentificacion.CC,
        ...     nombre="María González",
        ...     salario_basico=Decimal("3000000"),
        ...     tipo_contrato=TipoContrato.TERMINO_INDEFINIDO
        ... )
        >>> nomina = Nomina(empleado=empleado, periodo="2024-01")
        >>> resultado = calcular_nomina(nomina)
        >>> print(f"Neto: ${resultado.neto_pagar:,.0f}")
    """
    from .calculadora import CalculadoraNomina
    
    calculadora = CalculadoraNomina(nomina)
    return calculadora.calcular()


def calcular_prestaciones_sociales(
    empleado: EmpleadoConfig,
    fecha_inicio: date,
    fecha_fin: date,
    es_liquidacion_final: bool = False
) -> Dict[str, Decimal]:
    """
    Calcula prestaciones sociales (cesantías, intereses, prima, vacaciones) para un periodo.
    
    Args:
        empleado: Configuración del empleado
        fecha_inicio: Fecha inicial del periodo
        fecha_fin: Fecha final del periodo
        es_liquidacion_final: Si es liquidación definitiva del contrato
        
    Returns:
        Diccionario con conceptos de prestaciones sociales:
        - cesantias: Cesantías acumuladas
        - intereses_cesantias: Intereses sobre cesantías (12% anual)
        - prima: Prima de servicios
        - vacaciones: Vacaciones acumuladas
        
    Ejemplo:
        >>> from datetime import date
        >>> empleado = EmpleadoConfig(
        ...     identificacion="987654321",
        ...     tipo_identificacion=TipoIdentificacion.CC,
        ...     nombre="Carlos Ruiz",
        ...     salario_basico=Decimal("2500000"),
        ...     tipo_contrato=TipoContrato.TERMINO_FIJO
        ... )
        >>> prestaciones = calcular_prestaciones_sociales(
        ...     empleado,
        ...     fecha_inicio=date(2024, 1, 1),
        ...     fecha_fin=date(2024, 12, 31)
        ... )
        >>> print(f"Cesantías: ${prestaciones['cesantias']:,.0f}")
    """
    from .prestaciones import CalculadoraPrestaciones
    
    calculadora = CalculadoraPrestaciones(empleado)
    return calculadora.calcular_periodo(fecha_inicio, fecha_fin, es_liquidacion_final)


def calcular_aportes_pila(
    salario_base: Decimal,
    dias_trabajados: int = 30,
    nivel_riesgo: NivelRiesgoARL = NivelRiesgoARL.NIVEL_I,
    porcentaje_fondo_solidaridad: Decimal = Decimal("0")
) -> Dict[str, Dict[str, Decimal]]:
    """
    Calcula aportes a seguridad social (PILA): salud, pensión y ARL.
    
    Args:
        salario_base: Salario base de cotización
        dias_trabajados: Días trabajados en el mes (para proporcionalidad)
        nivel_riesgo: Nivel de riesgo ARL del empleado
        porcentaje_fondo_solidaridad: Porcentaje adicional para fondo solidaridad pensional
        
    Returns:
        Diccionario con aportes desglosados por empleado y empleador:
        {
            'salud': {'empleado': ..., 'empleador': ..., 'total': ...},
            'pension': {'empleado': ..., 'empleador': ..., 'total': ...},
            'arl': {'empleador': ..., 'total': ...},
            'fondo_solidaridad': {'empleado': ...}
        }
        
    Ejemplo:
        >>> aportes = calcular_aportes_pila(
        ...     salario_base=Decimal("3500000"),
        ...     dias_trabajados=30,
        ...     nivel_riesgo=NivelRiesgoARL.NIVEL_II
        ... )
        >>> print(f"Salud empleado: ${aportes['salud']['empleado']:,.0f}")
        >>> print(f"Pensión empleado: ${aportes['pension']['empleado']:,.0f}")
    """
    from .pila import CalculadoraPILA
    
    calculadora = CalculadoraPILA()
    return calculadora.calcular_aportes(
        salario_base,
        dias_trabajados,
        nivel_riesgo,
        porcentaje_fondo_solidaridad
    )


def calcular_retencion_fuente(
    salario_mensual: Decimal,
    otros_ingresos: Decimal = Decimal("0"),
    deducciones_permitidas: Decimal = Decimal("0"),
    dependientes: int = 0
) -> Decimal:
    """
    Calcula retención en la fuente según tabla UVT 2024.
    
    Args:
        salario_mensual: Ingreso laboral mensual
        otros_ingresos: Otros ingresos gravados del mes
        deducciones_permitidas: Deducciones permitidas (medicina prepagada, dependientes, etc.)
        dependientes: Número de dependientes (10% del ingreso por dependiente hasta límite)
        
    Returns:
        Valor de retención en la fuente a descontar
        
    Nota:
        Aplica tabla de retención en la fuente vigente 2024 con rangos UVT.
        No aplica para ingresos inferiores a 95 UVT mensuales.
        
    Ejemplo:
        >>> retencion = calcular_retencion_fuente(
        ...     salario_mensual=Decimal("8000000"),
        ...     dependientes=2
        ... )
        >>> print(f"Retención: ${retencion:,.0f}")
    """
    from .retencion import CalculadoraRetencion
    
    calculadora = CalculadoraRetencion()
    return calculadora.calcular(
        salario_mensual,
        otros_ingresos,
        deducciones_permitidas,
        dependientes
    )


def generar_xml_nomina(
    nomina: Nomina,
    resultado: ResultadoNomina,
    datos_empleador: Dict[str, str],
    numero_documento: str,
    prefijo: str = "NOM",
    cune: Optional[str] = None
) -> str:
    """
    Genera XML de nómina electrónica según resolución 000013 DIAN.
    
    Args:
        nomina: Objeto Nomina procesada
        resultado: Resultado del cálculo de nómina
        datos_empleador: Datos del empleador (NIT, razón social, dirección, etc.)
        numero_documento: Número consecutivo del documento
        prefijo: Prefijo del documento de nómina
        cune: Código Único de Nómina Electrónica (se genera si no se provee)
        
    Returns:
        String con XML completo listo para enviar a DIAN
        
    Raises:
        ValueError: Si faltan datos obligatorios del empleador
        
    Ejemplo:
        >>> empleador = {
        ...     'nit': '900123456',
        ...     'razon_social': 'Empresa XYZ S.A.S.',
        ...     'direccion': 'Calle 123 #45-67',
        ...     'ciudad': 'Bogotá',
        ...     'telefono': '6011234567'
        ... }
        >>> xml = generar_xml_nomina(
        ...     nomina=nomina,
        ...     resultado=resultado,
        ...     datos_empleador=empleador,
        ...     numero_documento="000123"
        ... )
        >>> with open("nomina_000123.xml", "w") as f:
        ...     f.write(xml)
    """
    from .xml_generator import GeneradorXMLNomina
    
    generador = GeneradorXMLNomina()
    return generador.generar(
        nomina,
        resultado,
        datos_empleador,
        numero_documento,
        prefijo,
        cune
    )


def liquidar_contrato(
    empleado: EmpleadoConfig,
    fecha_inicio: date,
    fecha_fin: date,
    motivo_terminacion: str,
    justa_causa: bool = False
) -> Dict[str, Any]:
    """
    Realiza liquidación final de contrato con todos los conceptos legales.
    
    Args:
        empleado: Configuración del empleado
        fecha_inicio: Fecha de inicio del contrato
        fecha_fin: Fecha de terminación del contrato
        motivo_terminacion: Motivo de terminación del contrato
        justa_causa: Si la terminación es por justa causa (afecta indemnización)
        
    Returns:
        Diccionario con conceptos de liquidación:
        - prestaciones_sociales: Cesantías, intereses, prima, vacaciones
        - indemnizacion: Indemnización según tipo de contrato y causa
        - total_liquidacion: Total a pagar en la liquidación
        
    Ejemplo:
        >>> liquidacion = liquidar_contrato(
        ...     empleado=empleado,
        ...     fecha_inicio=date(2020, 1, 15),
        ...     fecha_fin=date(2024, 1, 31),
        ...     motivo_terminacion="Renuncia voluntaria",
        ...     justa_causa=False
        ... )
        >>> print(f"Total liquidación: ${liquidacion['total_liquidacion']:,.0f}")
    """
    from .liquidacion import LiquidadorContrato
    
    liquidador = LiquidadorContrato(empleado)
    return liquidador.liquidar(fecha_inicio, fecha_fin, motivo_terminacion, justa_causa)


# Exportar clases y funciones principales
__all__ = [
    # Constantes
    "SALARIO_MINIMO_2024",
    "AUXILIO_TRANSPORTE_2024",
    "UVT_2024",
    
    # Enums
    "TipoIdentificacion",
    "TipoContrato",
    "NivelRiesgoARL",
    "TipoNovedad",
    
    # Clases principales
    "EmpleadoConfig",
    "Nomina",
    "ResultadoNomina",
    
    # Funciones de alto nivel
    "calcular_nomina",
    "calcular_prestaciones_sociales",
    "calcular_aportes_pila",
    "calcular_retencion_fuente",
    "generar_xml_nomina",
    "liquidar_contrato",
]