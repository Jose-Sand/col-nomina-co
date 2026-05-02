"""
Módulo para cálculo de retención en la fuente sobre salarios

Implementa el procedimiento 2 establecido en el artículo 383 del Estatuto Tributario
colombiano, utilizando la tabla de retención vigente 2024 con valores en UVT.

Referencias legales:
- Estatuto Tributario art. 383, 384, 385, 386, 387
- Resolución DIAN que actualiza UVT anualmente
- Concepto DIAN 100208192-1063 (procedimiento retención)
- Ley 2277 de 2022 (modificaciones recientes)

Autor: nomina-co
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


# Valor UVT 2024 según DIAN (actualizar cada año)
# Resolución 000006 del 19 de enero de 2024
UVT_2024 = Decimal("47065")

# Valores históricos para referencia
UVT_HISTORICO = {
    2024: Decimal("47065"),
    2023: Decimal("42412"),
    2022: Decimal("38004"),
    2021: Decimal("36308"),
}


class TipoPeriodo(str, Enum):
    """Tipo de periodo para cálculo de retención"""
    MENSUAL = "mensual"
    QUINCENAL = "quincenal"
    SEMANAL = "semanal"


class TablaPorcentajes(BaseModel):
    """
    Estructura de la tabla de retención en la fuente para empleados
    según Estatuto Tributario art. 383 (procedimiento 2)
    
    Rangos en UVT y porcentajes aplicables para 2024
    """
    desde_uvt: Decimal = Field(description="Límite inferior del rango en UVT")
    hasta_uvt: Optional[Decimal] = Field(
        None, 
        description="Límite superior del rango en UVT, None para infinito"
    )
    tarifa_marginal: Decimal = Field(
        description="Porcentaje de retención marginal (0-1)"
    )
    impuesto_base_uvt: Decimal = Field(
        default=Decimal("0"),
        description="Impuesto base del rango en UVT"
    )

    class Config:
        frozen = True


# Tabla oficial de retención año 2024
# Art. 241 ET modificado por Ley 2277 de 2022
TABLA_RETENCION_2024 = [
    TablaPorcentajes(
        desde_uvt=Decimal("0"),
        hasta_uvt=Decimal("95"),
        tarifa_marginal=Decimal("0"),
        impuesto_base_uvt=Decimal("0")
    ),
    TablaPorcentajes(
        desde_uvt=Decimal("95"),
        hasta_uvt=Decimal("150"),
        tarifa_marginal=Decimal("0.19"),
        impuesto_base_uvt=Decimal("0")
    ),
    TablaPorcentajes(
        desde_uvt=Decimal("150"),
        hasta_uvt=Decimal("360"),
        tarifa_marginal=Decimal("0.28"),
        impuesto_base_uvt=Decimal("10.45")
    ),
    TablaPorcentajes(
        desde_uvt=Decimal("360"),
        hasta_uvt=Decimal("640"),
        tarifa_marginal=Decimal("0.33"),
        impuesto_base_uvt=Decimal("69.25")
    ),
    TablaPorcentajes(
        desde_uvt=Decimal("640"),
        hasta_uvt=Decimal("945"),
        tarifa_marginal=Decimal("0.35"),
        impuesto_base_uvt=Decimal("161.65")
    ),
    TablaPorcentajes(
        desde_uvt=Decimal("945"),
        hasta_uvt=Decimal("2300"),
        tarifa_marginal=Decimal("0.37"),
        impuesto_base_uvt=Decimal("268.40")
    ),
    TablaPorcentajes(
        desde_uvt=Decimal("2300"),
        hasta_uvt=None,  # En adelante
        tarifa_marginal=Decimal("0.39"),
        impuesto_base_uvt=Decimal("769.85")
    ),
]


@dataclass
class BaseRetencion:
    """
    Clase base para almacenar componentes del cálculo de retención
    
    Atributos:
        ingresos_laborales: Total devengado sujeto a retención
        deducciones_permitidas: Suma de deducciones legales
        renta_exenta: Valor de rentas exentas aplicables
        base_retencion_uvt: Base en UVT sobre la que se calcula retención
        uvt_aplicado: Valor UVT usado en el cálculo
    """
    ingresos_laborales: Decimal
    deducciones_permitidas: Decimal
    renta_exenta: Decimal
    base_retencion_uvt: Decimal
    uvt_aplicado: Decimal


class ConceptoRetencion(BaseModel):
    """Representa un concepto que afecta la base de retención"""
    codigo: str = Field(description="Código del concepto")
    descripcion: str = Field(description="Descripción del concepto")
    valor: Decimal = Field(description="Valor en pesos colombianos")
    es_ingreso: bool = Field(
        default=True,
        description="True si suma a ingresos, False si es deducción"
    )

    @field_validator("valor")
    @classmethod
    def valor_no_negativo(cls, v: Decimal) -> Decimal:
        """Valida que el valor no sea negativo"""
        if v < 0:
            raise ValueError("El valor del concepto no puede ser negativo")
        return v


class CalculoRetencion(BaseModel):
    """
    Modelo para entrada de datos en cálculo de retención
    
    Incluye todos los conceptos necesarios para aplicar procedimiento 2
    según normativa DIAN vigente.
    """
    salario_basico: Decimal = Field(
        gt=0,
        description="Salario básico mensual del empleado"
    )
    periodo: TipoPeriodo = Field(
        default=TipoPeriodo.MENSUAL,
        description="Periodo de pago (mensual, quincenal, semanal)"
    )
    conceptos_adicionales: list[ConceptoRetencion] = Field(
        default_factory=list,
        description="Conceptos adicionales (comisiones, bonos, etc.)"
    )
    
    # Deducciones legales
    aporte_salud_empleado: Decimal = Field(
        default=Decimal("0"),
        description="Aporte obligatorio a salud (4% del IBC)"
    )
    aporte_pension_empleado: Decimal = Field(
        default=Decimal("0"),
        description="Aporte obligatorio a pensión (4% del IBC)"
    )
    aporte_fondo_solidaridad: Decimal = Field(
        default=Decimal("0"),
        description="Aporte solidaridad pensional si aplica"
    )
    
    # Deducciones voluntarias con límites
    pagos_salud_prepagada: Decimal = Field(
        default=Decimal("0"),
        description="Pagos medicina prepagada (límite 16 UVT mensuales)"
    )
    dependientes: int = Field(
        default=0,
        ge=0,
        le=10,
        description="Número de dependientes (máximo 10% de ingresos, 32 UVT c/u)"
    )
    interes_vivienda: Decimal = Field(
        default=Decimal("0"),
        description="Intereses por préstamo vivienda (límite 1200 UVT anuales)"
    )
    
    # Rentas exentas
    aporte_pension_voluntaria: Decimal = Field(
        default=Decimal("0"),
        description="Aportes voluntarios pensión (límite 30% del ingreso)"
    )
    aporte_afc: Decimal = Field(
        default=Decimal("0"),
        description="Aportes AFC (límite 30% del ingreso combinado con voluntaria)"
    )
    
    # Metadatos
    ano_gravable: int = Field(
        default_factory=lambda: date.today().year,
        description="Año gravable para cálculo"
    )
    uvt_personalizado: Optional[Decimal] = Field(
        None,
        description="Valor UVT específico, si difiere del oficial del año"
    )

    @field_validator("dependientes")
    @classmethod
    def validar_dependientes(cls, v: int) -> int:
        """Valida número de dependientes según normativa"""
        if v > 10:
            raise ValueError(
                "El número de dependientes no puede exceder 10 según DIAN"
            )
        return v

    @field_validator("aporte_salud_empleado", "aporte_pension_empleado")
    @classmethod
    def validar_aportes(cls, v: Decimal) -> Decimal:
        """Valida que los aportes no sean negativos"""
        if v < 0:
            raise ValueError("Los aportes obligatorios no pueden ser negativos")
        return v


class ResultadoRetencion(BaseModel):
    """
    Resultado completo del cálculo de retención en la fuente
    
    Incluye desglose detallado para auditoría y trazabilidad
    """
    # Valores base
    total_ingresos_laborales: Decimal = Field(
        description="Suma de todos los ingresos del periodo"
    )
    total_deducciones: Decimal = Field(
        description="Suma de deducciones permitidas aplicadas"
    )
    total_rentas_exentas: Decimal = Field(
        description="Suma de rentas exentas aplicadas"
    )
    
    # Cálculo en UVT
    base_retencion_pesos: Decimal = Field(
        description="Base de retención en pesos colombianos"
    )
    base_retencion_uvt: Decimal = Field(
        description="Base de retención convertida a UVT"
    )
    
    # Resultado final
    retencion_calculada: Decimal = Field(
        description="Valor de retención en pesos colombianos"
    )
    porcentaje_efectivo: Decimal = Field(
        description="Porcentaje efectivo de retención sobre ingresos"
    )
    
    # Desglose de deducciones
    desglose_deducciones: dict[str, Decimal] = Field(
        description="Detalle de cada tipo de deducción aplicada"
    )
    desglose_rentas_exentas: dict[str, Decimal] = Field(
        description="Detalle de cada renta exenta aplicada"
    )
    
    # Metadata
    uvt_utilizado: Decimal = Field(description="Valor UVT usado en el cálculo")
    periodo: TipoPeriodo = Field(description="Periodo calculado")
    fecha_calculo: date = Field(
        default_factory=date.today,
        description="Fecha de ejecución del cálculo"
    )
    tramo_aplicado: Optional[TablaPorcentajes] = Field(
        None,
        description="Tramo de la tabla usado en el cálculo"
    )
    
    # Flags de validación
    aplica_retencion: bool = Field(
        description="Indica si corresponde retención o está exento"
    )
    observaciones: list[str] = Field(
        default_factory=list,
        description="Notas sobre el cálculo (límites aplicados, ajustes, etc.)"
    )

    def porcentaje_nominal(self) -> Decimal:
        """
        Retorna el porcentaje nominal del tramo aplicado
        
        Returns:
            Porcentaje de la tabla si aplica retención, 0 en caso contrario
        """
        if self.tramo_aplicado:
            return self.tramo_aplicado.tarifa_marginal * Decimal("100")
        return Decimal("0")


def obtener_uvt(ano: int, uvt_personalizado: Optional[Decimal] = None) -> Decimal:
    """
    Obtiene el valor UVT para el año especificado
    
    Args:
        ano: Año gravable
        uvt_personalizado: Valor específico si se requiere override
        
    Returns:
        Valor UVT en pesos colombianos
        
    Raises:
        ValueError: Si el año no está disponible y no hay valor personalizado
    """
    if uvt_personalizado:
        return uvt_personalizado
    
    if ano not in UVT_HISTORICO:
        raise ValueError(
            f"Valor UVT para año {ano} no disponible. "
            f"Proporcione uvt_personalizado o actualice UVT_HISTORICO"
        )
    
    return UVT_HISTORICO[ano]


def calcular_deducciones_permitidas(
    calculo: CalculoRetencion,
    uvt: Decimal,
    periodo: TipoPeriodo
) -> tuple[Decimal, dict[str, Decimal]]:
    """
    Calcula el total de deducciones permitidas según art. 387 ET
    
    Aplica los límites legales establecidos por la DIAN:
    - Medicina prepagada: 16 UVT mensuales
    - Dependientes: 10% de ingresos, máx 32 UVT c/u mensual
    - Intereses vivienda: 100 UVT mensuales (1200 anuales)
    
    Args:
        calculo: Datos del cálculo con deducciones solicitadas
        uvt: Valor UVT del periodo
        periodo: Tipo de periodo de pago
        
    Returns:
        Tupla con (total_deducciones, desglose_por_concepto)
    """
    deducciones: dict[str, Decimal] = {}
    
    # Factor para ajustar límites según periodo
    factor_periodo = _obtener_factor_periodo(periodo)
    
    # Deducción 1: Aportes obligatorios (sin límite)
    aporte_salud = calculo.aporte_salud_empleado
    aporte_pension = calculo.aporte_pension_empleado
    aporte_solidaridad = calculo.aporte_fondo_solidaridad
    
    deducciones["aportes_salud"] = aporte_salud
    deducciones["aportes_pension"] = aporte_pension
    deducciones["fondo_solidaridad"] = aporte_solidaridad
    
    # Deducción 2: Medicina prepagada (límite 16 UVT mensuales)
    limite_prepagada = (uvt * Decimal("16") * factor_periodo).quantize(
        Decimal("0.01"), ROUND_HALF_UP
    )
    prepagada_deducible = min(calculo.pagos_salud_prepagada, limite_prepagada)
    deducciones["medicina_prepagada"] = prepagada_deducible
    
    # Deducción 3: Dependientes (32 UVT c/u, máx 10% ingresos)
    if calculo.dependientes > 0:
        total_ingresos = _calcular_total_ingresos(calculo)
        
        # Límite por UVT
        limite_uvt_dependientes = (
            uvt * Decimal("32") * Decimal(str(calculo.dependientes)) * factor_periodo
        ).quantize(Decimal("0.01"), ROUND_HALF_UP)
        
        # Límite por porcentaje de ingresos
        limite_porcentaje = (total_ingresos * Decimal("0.10")).quantize(
            Decimal("0.01"), ROUND_HALF_UP
        )
        
        dependientes_deducible = min(limite_uvt_dependientes, limite_porcentaje)
        deducciones["dependientes"] = dependientes_deducible
    
    # Deducción 4: Intereses vivienda (límite 100 UVT mensuales)
    limite_vivienda = (uvt * Decimal("100") * factor_periodo).quantize(
        Decimal("0.01"), ROUND_HALF_UP
    )
    vivienda_deducible = min(calculo.interes_vivienda, limite_vivienda)
    deducciones["intereses_vivienda"] = vivienda_deducible
    
    total = sum(deducciones.values())
    
    return total, deducciones


def calcular_rentas_exentas(
    calculo: CalculoRetencion,
    uvt: Decimal,
    periodo: TipoPeriodo
) -> tuple[Decimal, dict[str, Decimal]]:
    """
    Calcula rentas exentas según art. 126-1 y 126-4 ET
    
    Límites:
    - Pensión voluntaria + AFC: 30% del ingreso laboral o 3800 UVT anuales
    - Rentas exentas totales: 40% del ingreso o 1000 UVT mensuales (menor)
    
    Args:
        calculo: Datos del cálculo con rentas exentas solicitadas
        uvt: Valor UVT del periodo
        periodo: Tipo de periodo de pago
        
    Returns:
        Tupla con (total_rentas_exentas, desglose_por_concepto)
    """
    rentas: dict[str, Decimal] = {}
    factor_periodo = _obtener_factor_periodo(periodo)
    
    total_ingresos = _calcular_total_ingresos(calculo)
    
    # Límite conjunto pensión voluntaria + AFC: 30% del ingreso laboral
    limite_porcentaje_pension = (total_ingresos * Decimal("0.30")).quantize(
        Decimal("0.01"), ROUND_HALF_UP
    )
    
    # Límite anual convertido al periodo: 3800 UVT anuales
    limite_uvt_pension = (
        uvt * Decimal("3800") / Decimal("12") * factor_periodo
    ).quantize(Decimal("0.01"), ROUND_HALF_UP)
    
    total_pension_afc = calculo.aporte_pension_voluntaria + calculo.aporte_afc
    pension_afc_exento = min(
        total_pension_afc,
        limite_porcentaje_pension,
        limite_uvt_pension
    )
    
    if calculo.aporte_pension_voluntaria > 0:
        # Prorratear entre voluntaria y AFC si hay ambos
        if total_pension_afc > 0:
            proporcion_voluntaria = (
                calculo.aporte_pension_voluntaria / total_pension_afc
            )
            rentas["pension_voluntaria"] = (
                pension_afc_exento * proporcion_voluntaria
            ).quantize(Decimal("0.01"), ROUND_HALF_UP)
        else:
            rentas["pension_voluntaria"] = Decimal("0")
    
    if calculo.aporte_afc > 0:
        if total_pension_afc > 0:
            proporcion_afc = calculo.aporte_afc / total_pension_afc
            rentas["afc"] = (pension_afc_exento * proporcion_afc).quantize(
                Decimal("0.01"), ROUND_HALF_UP
            )
        else:
            rentas["afc"] = Decimal("0")
    
    # Aplicar límite global de rentas exentas: 40% o 1000 UVT mensuales
    limite_porcentaje_global = (total_ingresos * Decimal("0.40")).quantize(
        Decimal("0.01"), ROUND_HALF_UP
    )
    limite_uvt_global = (uvt * Decimal("1000") * factor_periodo).quantize(
        Decimal("0.01"), ROUND_HALF_UP
    )
    limite_global = min(limite_porcentaje_global, limite_uvt_global)
    
    total_rentas = sum(rentas.values())
    if total_rentas > limite_global:
        # Ajustar proporcionalmente si se excede el límite
        factor_ajuste = limite_global / total_rentas
        rentas = {
            k: (v * factor_ajuste).quantize(Decimal("0.01"), ROUND_HALF_UP)
            for k, v in rentas.items()
        }
        total_rentas = limite_global
    
    return total_rentas, rentas


def _calcular_total_ingresos(calculo: CalculoRetencion) -> Decimal:
    """
    Calcula el total de ingresos laborales del periodo
    
    Args:
        calculo: Datos del cálculo
        
    Returns:
        Total de ingresos en pesos
    """
    total = calculo.salario_basico
    
    for concepto in calculo.conceptos_adicionales:
        if concepto.es_ingreso:
            total += concepto.valor
    
    return total


def _obtener_factor_periodo(periodo: TipoPeriodo) -> Decimal:
    """
    Retorna el factor de ajuste según el periodo de pago
    
    Args:
        periodo: Tipo de periodo
        
    Returns:
        Factor multiplicador (mensual=1, quincenal=0.5, semanal=0.25)
    """
    factores = {
        TipoPeriodo.MENSUAL: Decimal("1"),
        TipoPeriodo.QUINCENAL: Decimal("0.5"),
        TipoPeriodo.SEMANAL: Decimal("0.25"),
    }
    return factores[periodo]


def encontrar_tramo_tabla(base_uvt: Decimal) -> TablaPorcentajes:
    """
    Encuentra el tramo correspondiente en la tabla de retención
    
    Args:
        base_uvt: Base gravable en UVT
        
    Returns:
        Tramo de la tabla aplicable
        
    Raises:
        ValueError: Si no se encuentra tramo (no debería ocurrir)
    """
    for tramo in TABLA_RETENCION_2024:
        if base_uvt >= tramo.desde_uvt:
            if tramo.hasta_uvt is None or base_uvt < tramo.hasta_uvt:
                return tramo
    
    # Último tramo (en adelante)
    return TABLA_RETENCION_2024[-1]


def calcular_retencion_procedimiento2(
    calculo: CalculoRetencion
) -> ResultadoRetencion:
    """
    Calcula la retención en la fuente usando procedimiento 2 (art. 383 ET)
    
    Este es el método principal de la librería. Implementa el procedimiento
    establecido por la DIAN para empleados, aplicando:
    
    1. Suma de ingresos laborales del mes
    2. Resta de deducciones permitidas (aportes, prepagada, dependientes, vivienda)
    3. Resta de rentas exentas (pensión voluntaria, AFC)
    4. Conversión a UVT
    5. Aplicación de tabla de retención
    6. Conversión resultado a pesos
    
    Args:
        calculo: Datos completos del empleado y periodo
        
    Returns:
        Resultado detallado con valor de retención y desglose
        
    Example:
        >>> from nomina_co.retencion import calcular_retencion_procedimiento2, CalculoRetencion
        >>> from decimal import Decimal
        >>> 
        >>> datos = CalculoRetencion(
        ...     salario_basico=Decimal("5000000"),
        ...     aporte_salud_empleado=Decimal("200000"),
        ...     aporte_pension_empleado=Decimal("200000"),
        ... )
        >>> resultado = calcular_retencion_procedimiento2(datos)
        >>> print(f"Retención: ${resultado.retencion_calculada:,.0f}")
    """
    observaciones: list[str] = []
    
    # Paso 1: Obtener UVT del periodo
    uvt = obtener_uvt(calculo.ano_gravable, calculo.uvt_personalizado)
    
    # Paso 2: Calcular total de ingresos laborales
    total_ingresos = _calcular_total_ingresos(calculo)
    
    # Paso 3: Calcular deducciones permitidas
    total_deducciones, desglose_deducciones = calcular_deducciones_permitidas(
        calculo, uvt, calculo.periodo
    )
    
    # Paso 4: Calcular rentas exentas
    total_rentas_exentas, desglose_rentas = calcular_rentas_exentas(
        calculo, uvt, calculo.periodo
    )
    
    # Paso 5: Calcular base de retención
    base_retencion = total_ingresos - total_deducciones - total_rentas_exentas
    
    # Ajustar si la base es negativa
    if base_retencion < 0:
        base_retencion = Decimal("0")
        observaciones.append(
            "Base de retención ajustada a cero por exceso de deducciones/exenciones"
        )
    
    # Paso 6: Convertir base a UVT
    base_uvt = (base_retencion / uvt).quantize(
        Decimal("0.01"), ROUND_HALF_UP
    )
    
    # Paso 7: Determinar si aplica retención
    # Según tabla 2024, se retiene desde 95 UVT
    if base_uvt < Decimal("95"):
        observaciones.append(
            f"Base de {base_uvt} UVT no alcanza mínimo de 95 UVT para retención"
        )
        
        return ResultadoRetencion(
            total_ingresos_laborales=total_ingresos,
            total_deducciones=total_deducciones,
            total_rentas_exentas=total_rentas_exentas,
            base_retencion_pesos=base_retencion,
            base_retencion_uvt=base_uvt,
            retencion_calculada=Decimal("0"),
            porcentaje_efectivo=Decimal("0"),
            desglose_deducciones=desglose_deducciones,
            desglose_rentas_exentas=desglose_rentas,
            uvt_utilizado=uvt,
            periodo=calculo.periodo,
            aplica_retencion=False,
            observaciones=observaciones,
        )
    
    # Paso 8: Encontrar tramo en la tabla
    tramo = encontrar_tramo_tabla(base_uvt)
    
    # Paso 9: Calcular retención en UVT
    # Fórmula: (Base_UVT - Desde_UVT) * Tarifa_Marginal + Impuesto_Base
    exceso_uvt = base_uvt - tramo.desde_uvt
    retencion_uvt = (exceso_uvt * tramo.tarifa_marginal) + tramo.impuesto_base_uvt
    
    # Paso 10: Convertir a pesos y redondear
    retencion_pesos = (retencion_uvt * uvt).quantize(
        Decimal("1"), ROUND_HALF_UP  # Pesos enteros
    )
    
    # Paso 11: Calcular porcentaje efectivo
    porcentaje_efectivo = (
        (retencion_pesos / total_ingresos * Decimal("100"))
        if total_ingresos > 0
        else Decimal("0")
    ).quantize(Decimal("0.01"), ROUND_HALF_UP)
    
    observaciones.append(
        f"Aplicado tramo {tramo.desde_uvt}-"
        f"{tramo.hasta_uvt or 'en adelante'} UVT "
        f"con tarifa marginal {tramo.tarifa_marginal * 100}%"
    )
    
    return ResultadoRetencion(
        total_ingresos_laborales=total_ingresos,
        total_deducciones=total_deducciones,
        total_rentas_exentas=total_rentas_exentas,
        base_retencion_pesos=base_retencion,
        base_retencion_uvt=base_uvt,
        retencion_calculada=retencion_pesos,
        porcentaje_efectivo=porcentaje_efectivo,
        desglose_deducciones=desglose_deducciones,
        desglose_rentas_exentas=desglose_rentas,
        uvt_utilizado=uvt,
        periodo=calculo.periodo,
        tramo_aplicado=tramo,
        aplica_retencion=True,
        observaciones=observaciones,
    )


def calcular_retencion_simplificada(
    salario_mensual: Decimal,
    ano: int = 2024,
    dependientes: int = 0
) -> Decimal:
    """
    Cálculo simplificado de retención para casos básicos
    
    Asume:
    - Solo salario básico sin conceptos adicionales
    - Aportes obligatorios estándar (4% salud + 4% pensión)
    - Sin deducciones voluntarias adicionales
    - Sin rentas exentas
    
    Args:
        salario_mensual: Salario básico mensual
        ano: Año gravable (default 2024)
        dependientes: Número de dependientes
        
    Returns:
        Valor de retención en pesos
        
    Example:
        >>> from nomina_co.retencion import calcular_retencion_simplificada
        >>> from decimal import Decimal
        >>> retencion = calcular_retencion_simplificada(Decimal("8000000"))
        >>> print(f"Retención: ${retencion:,.0f}")
    """
    # Calcular aportes obligatorios
    aporte_salud = (salario_mensual * Decimal("0.04")).quantize(
        Decimal("0.01"), ROUND_HALF_UP
    )
    aporte_pension = (salario_mensual * Decimal("0.04")).quantize(
        Decimal("0.01"), ROUND_HALF_UP
    )
    
    # Crear objeto de cálculo
    calculo = CalculoRetencion(
        salario_basico=salario_mensual,
        aporte_salud_empleado=aporte_salud,
        aporte_pension_empleado=aporte_pension,
        dependientes=dependientes,
        ano_gravable=ano,
    )
    
    # Calcular
    resultado = calcular_retencion_procedimiento2(calculo)
    
    return resultado.retencion_calculada


def verificar_limites_legales(calculo: CalculoRetencion) -> list[str]: