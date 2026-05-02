"""
Módulo para cálculo de aportes a seguridad social PILA y parafiscales

Calcula los aportes obligatorios según la normativa colombiana:
- Salud: 12.5% (empleador 8.5%, empleado 4%)
- Pensión: 16% (empleador 12%, empleado 4%)
- ARL: según nivel de riesgo (100% empleador)
- Parafiscales: SENA 2%, ICBF 3%, Cajas 4% (sobre salarios < 10 SMMLV)
- Fondo de Solidaridad Pensional: para salarios >= 4 SMMLV

Referencias:
- Ley 100 de 1993 (Sistema de Seguridad Social)
- Ley 1122 de 2007 (Reforma salud)
- Decreto 1295 de 1994 (ARL)
- Ley 1607 de 2012 (Reforma tributaria - parafiscales)
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, validator


class NivelRiesgoARL(Enum):
    """
    Niveles de riesgo laboral según clasificación DIAN
    
    Cada nivel tiene una tarifa de cotización diferente.
    Decreto 1295 de 1994 y actualizaciones posteriores.
    """
    NIVEL_I = 1    # Riesgo mínimo: 0.522%
    NIVEL_II = 2   # Riesgo bajo: 1.044%
    NIVEL_III = 3  # Riesgo medio: 2.436%
    NIVEL_IV = 4   # Riesgo alto: 4.350%
    NIVEL_V = 5    # Riesgo máximo: 6.960%


# Tarifas ARL vigentes según nivel de riesgo (porcentaje sobre IBC)
TARIFAS_ARL = {
    NivelRiesgoARL.NIVEL_I: Decimal("0.522"),
    NivelRiesgoARL.NIVEL_II: Decimal("1.044"),
    NivelRiesgoARL.NIVEL_III: Decimal("2.436"),
    NivelRiesgoARL.NIVEL_IV: Decimal("4.350"),
    NivelRiesgoARL.NIVEL_V: Decimal("6.960"),
}


class TipoContribuyente(Enum):
    """
    Tipo de contribuyente para determinar obligación de parafiscales
    
    Ley 1607 de 2012: solo empresas con más de cierto tamaño o actividad
    específica pagan parafiscales completos.
    """
    EMPLEADO = "empleado"
    EMPLEADOR_PEQUENO = "empleador_pequeno"  # No paga parafiscales
    EMPLEADOR_GRANDE = "empleador_grande"    # Paga parafiscales completos


@dataclass
class SalarioMinimo:
    """
    Salario mínimo legal mensual vigente y auxilio de transporte
    
    Estos valores se actualizan anualmente mediante decreto gubernamental.
    """
    valor: Decimal
    auxilio_transporte: Decimal
    ano: int
    
    @classmethod
    def actual(cls, ano_actual: int = 2024) -> "SalarioMinimo":
        """
        Retorna el salario mínimo vigente para el año especificado
        
        Args:
            ano_actual: Año de consulta (default 2024)
            
        Returns:
            Instancia con valores vigentes
            
        Note:
            Actualizar estos valores cada año según decreto oficial
        """
        valores_historicos = {
            2024: {"salario": Decimal("1300000"), "auxilio": Decimal("162000")},
            2023: {"salario": Decimal("1160000"), "auxilio": Decimal("140606")},
            2022: {"salario": Decimal("1000000"), "auxilio": Decimal("117172")},
        }
        
        valores = valores_historicos.get(ano_actual)
        if not valores:
            raise ValueError(f"No hay salario mínimo configurado para el año {ano_actual}")
        
        return cls(
            valor=valores["salario"],
            auxilio_transporte=valores["auxilio"],
            ano=ano_actual
        )


class BaseAportes(BaseModel):
    """
    Datos base para cálculo de aportes a seguridad social
    
    El IBC (Ingreso Base de Cotización) debe calcularse previamente
    incluyendo todos los conceptos salariales del mes.
    """
    ibc_salud: Decimal = Field(..., description="Ingreso Base de Cotización para salud")
    ibc_pension: Decimal = Field(..., description="Ingreso Base de Cotización para pensión")
    ibc_riesgos: Decimal = Field(..., description="Ingreso Base de Cotización para ARL")
    nivel_riesgo: NivelRiesgoARL = Field(..., description="Nivel de riesgo laboral del cargo")
    salario_basico: Decimal = Field(..., description="Salario básico mensual del empleado")
    dias_trabajados: int = Field(30, ge=1, le=30, description="Días trabajados en el mes")
    aplica_parafiscales: bool = Field(False, description="Si el empleador debe pagar parafiscales")
    salario_integral: bool = Field(False, description="Si el salario es integral (> 10 SMMLV)")
    
    class Config:
        use_enum_values = False
    
    @validator("ibc_salud", "ibc_pension", "ibc_riesgos", "salario_basico")
    def validar_montos_positivos(cls, valor: Decimal) -> Decimal:
        """Valida que los montos sean positivos"""
        if valor < 0:
            raise ValueError("Los montos de cotización deben ser positivos")
        return valor
    
    @validator("ibc_salud", "ibc_pension")
    def validar_topes_ibc(cls, valor: Decimal, values: dict) -> Decimal:
        """
        Valida topes mínimos y máximos del IBC
        
        - Mínimo: 1 SMMLV (salvo casos especiales medio tiempo)
        - Máximo salud: sin tope
        - Máximo pensión: 25 SMMLV
        """
        smmlv = SalarioMinimo.actual().valor
        
        # El tope máximo de pensión es 25 SMMLV
        if "ibc_pension" in values.keys() and valor > smmlv * 25:
            raise ValueError(f"IBC de pensión no puede exceder 25 SMMLV ({smmlv * 25})")
        
        return valor


class AportesSalud(BaseModel):
    """Detalle de aportes a salud (EPS)"""
    empleado: Decimal = Field(..., description="Aporte empleado (4% del IBC)")
    empleador: Decimal = Field(..., description="Aporte empleador (8.5% del IBC)")
    total: Decimal = Field(..., description="Total aporte salud (12.5%)")
    ibc: Decimal = Field(..., description="Ingreso base de cotización usado")


class AportesPension(BaseModel):
    """Detalle de aportes a pensión"""
    empleado: Decimal = Field(..., description="Aporte empleado (4% del IBC)")
    empleador: Decimal = Field(..., description="Aporte empleador (12% del IBC)")
    fondo_solidaridad: Decimal = Field(Decimal("0"), description="Fondo Solidaridad Pensional")
    subsistencia: Decimal = Field(Decimal("0"), description="Aporte subsistencia (> 16 SMMLV)")
    total: Decimal = Field(..., description="Total aporte pensión (16% + FSP)")
    ibc: Decimal = Field(..., description="Ingreso base de cotización usado")


class AportesRiesgos(BaseModel):
    """Detalle de aportes a ARL (100% empleador)"""
    empleador: Decimal = Field(..., description="Aporte empleador según nivel de riesgo")
    nivel_riesgo: NivelRiesgoARL = Field(..., description="Nivel de riesgo aplicado")
    tarifa: Decimal = Field(..., description="Tarifa aplicada (porcentaje)")
    ibc: Decimal = Field(..., description="Ingreso base de cotización usado")
    
    class Config:
        use_enum_values = False


class AportesParafiscales(BaseModel):
    """Detalle de aportes parafiscales (solo empleadores obligados)"""
    sena: Decimal = Field(Decimal("0"), description="SENA 2% (empleador)")
    icbf: Decimal = Field(Decimal("0"), description="ICBF 3% (empleador)")
    caja_compensacion: Decimal = Field(Decimal("0"), description="Caja Compensación 4% (empleador)")
    total: Decimal = Field(Decimal("0"), description="Total parafiscales")
    aplica: bool = Field(False, description="Si aplican parafiscales")


class ResumenAportes(BaseModel):
    """
    Resumen completo de aportes de seguridad social PILA
    
    Este modelo contiene el detalle completo de todos los aportes
    obligatorios para un empleado en un período de nómina.
    """
    salud: AportesSalud
    pension: AportesPension
    riesgos: AportesRiesgos
    parafiscales: AportesParafiscales
    
    total_empleado: Decimal = Field(..., description="Total deducciones al empleado")
    total_empleador: Decimal = Field(..., description="Total costo para empleador")
    total_general: Decimal = Field(..., description="Total aportes (empleado + empleador)")
    
    dias_cotizados: int = Field(..., description="Días cotizados en el período")
    fecha_calculo: date = Field(default_factory=date.today, description="Fecha de cálculo")


def calcular_salud(ibc: Decimal) -> AportesSalud:
    """
    Calcula aportes a salud (EPS)
    
    Distribución:
    - Empleado: 4% del IBC
    - Empleador: 8.5% del IBC
    - Total: 12.5% del IBC
    
    Args:
        ibc: Ingreso Base de Cotización para salud
        
    Returns:
        Detalle de aportes a salud
        
    Note:
        No hay tope máximo para el IBC de salud
    """
    empleado = (ibc * Decimal("4.0") / Decimal("100")).quantize(Decimal("0.01"))
    empleador = (ibc * Decimal("8.5") / Decimal("100")).quantize(Decimal("0.01"))
    total = empleado + empleador
    
    return AportesSalud(
        empleado=empleado,
        empleador=empleador,
        total=total,
        ibc=ibc
    )


def calcular_pension(
    ibc: Decimal,
    salario_basico: Decimal,
    salario_integral: bool = False
) -> AportesPension:
    """
    Calcula aportes a pensión con Fondo de Solidaridad Pensional
    
    Distribución base:
    - Empleado: 4% del IBC
    - Empleador: 12% del IBC
    - Total: 16% del IBC
    
    Fondo de Solidaridad Pensional (FSP):
    - De 4 a 16 SMMLV: 1% adicional (empleado)
    - De 16 a 17 SMMLV: 1.2% adicional
    - De 17 a 18 SMMLV: 1.4% adicional
    - De 18 a 19 SMMLV: 1.6% adicional
    - De 19 a 20 SMMLV: 1.8% adicional
    - Más de 20 SMMLV: 2% adicional
    
    Aporte subsistencia (> 16 SMMLV):
    - Empleador: 1% adicional
    
    Args:
        ibc: Ingreso Base de Cotización para pensión (máx 25 SMMLV)
        salario_basico: Salario básico del empleado
        salario_integral: Si es salario integral
        
    Returns:
        Detalle de aportes a pensión
    """
    smmlv = SalarioMinimo.actual().valor
    
    # Aportes base
    empleado_base = (ibc * Decimal("4.0") / Decimal("100")).quantize(Decimal("0.01"))
    empleador_base = (ibc * Decimal("12.0") / Decimal("100")).quantize(Decimal("0.01"))
    
    # Fondo de Solidaridad Pensional (sobre el IBC)
    fondo_solidaridad = Decimal("0")
    subsistencia = Decimal("0")
    
    # Calcular múltiplo de SMMLV del salario básico
    multiplo_smmlv = salario_basico / smmlv
    
    if multiplo_smmlv >= 4:
        if multiplo_smmlv < 16:
            fondo_solidaridad = (ibc * Decimal("1.0") / Decimal("100")).quantize(Decimal("0.01"))
        elif multiplo_smmlv < 17:
            fondo_solidaridad = (ibc * Decimal("1.2") / Decimal("100")).quantize(Decimal("0.01"))
            subsistencia = (ibc * Decimal("1.0") / Decimal("100")).quantize(Decimal("0.01"))
        elif multiplo_smmlv < 18:
            fondo_solidaridad = (ibc * Decimal("1.4") / Decimal("100")).quantize(Decimal("0.01"))
            subsistencia = (ibc * Decimal("1.0") / Decimal("100")).quantize(Decimal("0.01"))
        elif multiplo_smmlv < 19:
            fondo_solidaridad = (ibc * Decimal("1.6") / Decimal("100")).quantize(Decimal("0.01"))
            subsistencia = (ibc * Decimal("1.0") / Decimal("100")).quantize(Decimal("0.01"))
        elif multiplo_smmlv < 20:
            fondo_solidaridad = (ibc * Decimal("1.8") / Decimal("100")).quantize(Decimal("0.01"))
            subsistencia = (ibc * Decimal("1.0") / Decimal("100")).quantize(Decimal("0.01"))
        else:
            fondo_solidaridad = (ibc * Decimal("2.0") / Decimal("100")).quantize(Decimal("0.01"))
            subsistencia = (ibc * Decimal("1.0") / Decimal("100")).quantize(Decimal("0.01"))
    
    empleado_total = empleado_base + fondo_solidaridad
    empleador_total = empleador_base + subsistencia
    total = empleado_total + empleador_total
    
    return AportesPension(
        empleado=empleado_total,
        empleador=empleador_total,
        fondo_solidaridad=fondo_solidaridad,
        subsistencia=subsistencia,
        total=total,
        ibc=ibc
    )


def calcular_arl(ibc: Decimal, nivel_riesgo: NivelRiesgoARL) -> AportesRiesgos:
    """
    Calcula aportes a ARL según nivel de riesgo
    
    El aporte a riesgos laborales es 100% a cargo del empleador.
    La tarifa depende del nivel de riesgo de la actividad económica.
    
    Args:
        ibc: Ingreso Base de Cotización para riesgos
        nivel_riesgo: Nivel de riesgo I a V
        
    Returns:
        Detalle de aportes a riesgos laborales
    """
    tarifa = TARIFAS_ARL[nivel_riesgo]
    empleador = (ibc * tarifa / Decimal("100")).quantize(Decimal("0.01"))
    
    return AportesRiesgos(
        empleador=empleador,
        nivel_riesgo=nivel_riesgo,
        tarifa=tarifa,
        ibc=ibc
    )


def calcular_parafiscales(
    salario_basico: Decimal,
    aplica: bool,
    salario_integral: bool = False
) -> AportesParafiscales:
    """
    Calcula aportes parafiscales (SENA, ICBF, Caja de Compensación)
    
    Según Ley 1607 de 2012 y modificaciones:
    - Solo aplica a empleadores que superen ciertos umbrales
    - No aplica a salarios >= 10 SMMLV
    - Sobre salario básico (no sobre IBC)
    
    Distribución (100% empleador):
    - SENA: 2%
    - ICBF: 3%
    - Caja de Compensación: 4%
    
    Args:
        salario_basico: Salario básico mensual
        aplica: Si el empleador está obligado a parafiscales
        salario_integral: Si es salario integral
        
    Returns:
        Detalle de aportes parafiscales
    """
    if not aplica or salario_integral:
        return AportesParafiscales(
            sena=Decimal("0"),
            icbf=Decimal("0"),
            caja_compensacion=Decimal("0"),
            total=Decimal("0"),
            aplica=False
        )
    
    smmlv = SalarioMinimo.actual().valor
    
    # No aplica parafiscales (SENA e ICBF) para salarios >= 10 SMMLV
    # Caja de Compensación siempre aplica si el empleador está obligado
    if salario_basico >= smmlv * 10:
        caja = (salario_basico * Decimal("4.0") / Decimal("100")).quantize(Decimal("0.01"))
        return AportesParafiscales(
            sena=Decimal("0"),
            icbf=Decimal("0"),
            caja_compensacion=caja,
            total=caja,
            aplica=True
        )
    
    sena = (salario_basico * Decimal("2.0") / Decimal("100")).quantize(Decimal("0.01"))
    icbf = (salario_basico * Decimal("3.0") / Decimal("100")).quantize(Decimal("0.01"))
    caja = (salario_basico * Decimal("4.0") / Decimal("100")).quantize(Decimal("0.01"))
    total = sena + icbf + caja
    
    return AportesParafiscales(
        sena=sena,
        icbf=icbf,
        caja_compensacion=caja,
        total=total,
        aplica=True
    )


def calcular_aportes_seguridad_social(base: BaseAportes) -> ResumenAportes:
    """
    Calcula todos los aportes de seguridad social y parafiscales
    
    Esta es la función principal que coordina el cálculo de todos
    los componentes de aportes PILA.
    
    Args:
        base: Datos base para el cálculo de aportes
        
    Returns:
        Resumen completo con todos los aportes calculados
        
    Example:
        >>> from decimal import Decimal
        >>> base = BaseAportes(
        ...     ibc_salud=Decimal("2000000"),
        ...     ibc_pension=Decimal("2000000"),
        ...     ibc_riesgos=Decimal("2000000"),
        ...     nivel_riesgo=NivelRiesgoARL.NIVEL_I,
        ...     salario_basico=Decimal("2000000"),
        ...     dias_trabajados=30,
        ...     aplica_parafiscales=True,
        ...     salario_integral=False
        ... )
        >>> resumen = calcular_aportes_seguridad_social(base)
        >>> print(f"Total empleado: ${resumen.total_empleado:,.0f}")
        >>> print(f"Total empleador: ${resumen.total_empleador:,.0f}")
    """
    # Calcular cada componente
    salud = calcular_salud(base.ibc_salud)
    pension = calcular_pension(
        base.ibc_pension,
        base.salario_basico,
        base.salario_integral
    )
    riesgos = calcular_arl(base.ibc_riesgos, base.nivel_riesgo)
    parafiscales = calcular_parafiscales(
        base.salario_basico,
        base.aplica_parafiscales,
        base.salario_integral
    )
    
    # Totales empleado (deducciones)
    total_empleado = salud.empleado + pension.empleado
    
    # Totales empleador (costos)
    total_empleador = (
        salud.empleador +
        pension.empleador +
        riesgos.empleador +
        parafiscales.total
    )
    
    # Total general
    total_general = total_empleado + total_empleador
    
    return ResumenAportes(
        salud=salud,
        pension=pension,
        riesgos=riesgos,
        parafiscales=parafiscales,
        total_empleado=total_empleado,
        total_empleador=total_empleador,
        total_general=total_general,
        dias_cotizados=base.dias_trabajados,
        fecha_calculo=date.today()
    )


def calcular_ibc(
    salario_basico: Decimal,
    horas_extras: Decimal = Decimal("0"),
    comisiones: Decimal = Decimal("0"),
    bonificaciones: Decimal = Decimal("0"),
    auxilio_transporte_incluir: bool = True,
    dias_trabajados: int = 30
) -> Decimal:
    """
    Calcula el Ingreso Base de Cotización (IBC)
    
    El IBC incluye todos los pagos que constituyen salario según
    el Código Sustantivo del Trabajo.
    
    Conceptos que conforman el IBC:
    - Salario básico
    - Horas extras
    - Comisiones
    - Bonificaciones habituales
    - Auxilio de transporte (si salario < 2 SMMLV)
    
    Args:
        salario_basico: Salario básico mensual
        horas_extras: Valor total horas extras del mes
        comisiones: Comisiones del mes
        bonificaciones: Bonificaciones salariales
        auxilio_transporte_incluir: Si incluir auxilio de transporte
        dias_trabajados: Días trabajados en el mes (para proporcional)
        
    Returns:
        IBC calculado
        
    Note:
        Si días trabajados < 30, el IBC se proporciona
    """
    smmlv = SalarioMinimo.actual().valor
    auxilio = SalarioMinimo.actual().auxilio_transporte
    
    ibc = salario_basico + horas_extras + comisiones + bonificaciones
    
    # Auxilio de transporte solo si salario < 2 SMMLV
    if auxilio_transporte_incluir and salario_basico < (smmlv * 2):
        ibc += auxilio
    
    # Proporcionar por días trabajados
    if dias_trabajados < 30:
        ibc = (ibc * dias_trabajados / 30).quantize(Decimal("0.01"))
    
    # Validar IBC mínimo (1 SMMLV proporcional)
    ibc_minimo = (smmlv * dias_trabajados / 30).quantize(Decimal("0.01"))
    if ibc < ibc_minimo:
        ibc = ibc_minimo
    
    return ibc


def validar_topes_ibc_pension(ibc: Decimal) -> Decimal:
    """
    Aplica el tope máximo de IBC para pensión (25 SMMLV)
    
    Args:
        ibc: IBC calculado
        
    Returns:
        IBC ajustado al tope si excede
    """
    smmlv = SalarioMinimo.actual().valor
    tope_maximo = smmlv * 25
    
    if ibc > tope_maximo:
        return tope_maximo
    
    return ibc