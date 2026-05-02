"""
Modelos Pydantic para validación de datos de nómina colombiana

Define las estructuras de datos para empleados, conceptos, devengados y deducciones
según los requerimientos de la DIAN y normativa laboral colombiana.
"""

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator, ConfigDict, computed_field


class TipoDocumento(str, Enum):
    """Tipos de documento de identidad válidos en Colombia"""
    CC = "CC"  # Cédula de ciudadanía
    CE = "CE"  # Cédula de extranjería
    PA = "PA"  # Pasaporte
    TI = "TI"  # Tarjeta de identidad
    NIT = "NIT"  # Número de identificación tributaria
    PEP = "PEP"  # Permiso especial de permanencia


class TipoContrato(str, Enum):
    """Tipos de contrato laboral según normativa colombiana"""
    INDEFINIDO = "indefinido"
    FIJO = "fijo"
    OBRA_LABOR = "obra_labor"
    APRENDIZAJE = "aprendizaje"
    PRESTACION_SERVICIOS = "prestacion_servicios"


class TipoTrabajador(str, Enum):
    """Clasificación de trabajadores según PILA"""
    DEPENDIENTE = "dependiente"
    INDEPENDIENTE = "independiente"
    APRENDIZ = "aprendiz"


class SubtipoTrabajador(str, Enum):
    """Subtipos de trabajador según PILA"""
    COTIZANTE = "01"  # Cotizante
    PENSIONADO_ACTIVO = "02"  # Pensionado que labora
    BENEFICIARIO_UPC_ADICIONAL = "03"  # Beneficiario UPC adicional


class NivelRiesgoARL(int, Enum):
    """Niveles de riesgo laboral ARL (I a V)"""
    RIESGO_I = 1  # Mínimo: 0.522%
    RIESGO_II = 2  # Bajo: 1.044%
    RIESGO_III = 3  # Medio: 2.436%
    RIESGO_IV = 4  # Alto: 4.350%
    RIESGO_V = 5  # Máximo: 6.960%


class TipoPeriodo(str, Enum):
    """Tipos de periodo de pago de nómina"""
    QUINCENAL = "quincenal"
    MENSUAL = "mensual"
    SEMANAL = "semanal"
    DECENAL = "decenal"


class TipoNovedad(str, Enum):
    """Tipos de novedades en nómina"""
    INCAPACIDAD = "incapacidad"
    LICENCIA_MATERNIDAD = "licencia_maternidad"
    LICENCIA_PATERNIDAD = "licencia_paternidad"
    LICENCIA_NO_REMUNERADA = "licencia_no_remunerada"
    VACACIONES = "vacaciones"
    SUSPENSION = "suspension"


class TipoHoraExtra(str, Enum):
    """Tipos de horas extra según legislación colombiana"""
    DIURNA = "diurna"  # Recargo 25%
    NOCTURNA = "nocturna"  # Recargo 75%
    DOMINICAL_DIURNA = "dominical_diurna"  # Recargo 75%
    DOMINICAL_NOCTURNA = "dominical_nocturna"  # Recargo 110%


class ConfiguracionEmpresa(BaseModel):
    """Configuración de la empresa para cálculo de nómina"""
    
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        use_enum_values=False
    )
    
    nit: str = Field(..., description="NIT de la empresa sin dígito de verificación")
    digito_verificacion: str = Field(..., description="Dígito de verificación del NIT")
    razon_social: str = Field(..., min_length=1, max_length=450)
    departamento: str = Field(..., description="Código DANE del departamento")
    municipio: str = Field(..., description="Código DANE del municipio")
    direccion: str = Field(..., min_length=1)
    
    # Configuración parafiscales
    aplica_parafiscales: bool = Field(
        default=True,
        description="Si aplica aportes parafiscales (depende de ingresos y cantidad empleados)"
    )
    
    # Tasa ARL promedio si la empresa tiene diferentes centros de trabajo
    tasa_arl_default: Optional[Decimal] = Field(
        default=None,
        ge=Decimal("0.00522"),
        le=Decimal("0.06960"),
        description="Tasa ARL por defecto si no se especifica por empleado"
    )
    
    @field_validator("nit")
    @classmethod
    def validar_nit(cls, v: str) -> str:
        """Valida formato NIT colombiano"""
        if not v.isdigit():
            raise ValueError("El NIT debe contener solo dígitos")
        if len(v) < 8 or len(v) > 10:
            raise ValueError("El NIT debe tener entre 8 y 10 dígitos")
        return v
    
    @field_validator("digito_verificacion")
    @classmethod
    def validar_dv(cls, v: str) -> str:
        """Valida dígito de verificación"""
        if not v.isdigit() or len(v) != 1:
            raise ValueError("El dígito de verificación debe ser un solo dígito")
        return v


class Empleado(BaseModel):
    """Modelo de empleado con todos los campos necesarios para liquidación"""
    
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        use_enum_values=False
    )
    
    # Identificación
    tipo_documento: TipoDocumento
    numero_documento: str = Field(..., min_length=5, max_length=15)
    primer_apellido: str = Field(..., min_length=1, max_length=60)
    segundo_apellido: Optional[str] = Field(default=None, max_length=60)
    primer_nombre: str = Field(..., min_length=1, max_length=60)
    segundo_nombre: Optional[str] = Field(default=None, max_length=60)
    
    # Información laboral
    tipo_contrato: TipoContrato
    tipo_trabajador: TipoTrabajador = Field(default=TipoTrabajador.DEPENDIENTE)
    subtipo_trabajador: SubtipoTrabajador = Field(default=SubtipoTrabajador.COTIZANTE)
    fecha_ingreso: date = Field(..., description="Fecha de ingreso a la empresa")
    fecha_retiro: Optional[date] = Field(default=None, description="Fecha de retiro si aplica")
    
    # Salario y compensación
    salario_basico: Decimal = Field(..., gt=0, description="Salario mensual básico")
    es_salario_integral: bool = Field(
        default=False,
        description="Si el salario es integral (>= 13 SMMLV)"
    )
    
    # Riesgo laboral
    nivel_riesgo_arl: NivelRiesgoARL = Field(default=NivelRiesgoARL.RIESGO_I)
    
    # Información para seguridad social
    eps_codigo: Optional[str] = Field(default=None, description="Código EPS según PILA")
    afp_codigo: Optional[str] = Field(default=None, description="Código AFP según PILA")
    arl_codigo: Optional[str] = Field(default=None, description="Código ARL según PILA")
    
    # Deducciones voluntarias
    aportes_voluntarios_pension: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description="Aportes voluntarios a pensión para deducción de base retención"
    )
    
    # Datos bancarios
    banco: Optional[str] = Field(default=None)
    tipo_cuenta: Optional[str] = Field(default=None, pattern="^(ahorros|corriente)$")
    numero_cuenta: Optional[str] = Field(default=None)
    
    # Contacto
    email: Optional[str] = Field(default=None)
    telefono: Optional[str] = Field(default=None)
    
    # Ubicación
    departamento: Optional[str] = Field(default=None, description="Código DANE departamento")
    municipio: Optional[str] = Field(default=None, description="Código DANE municipio")
    direccion: Optional[str] = Field(default=None)
    
    @field_validator("numero_documento")
    @classmethod
    def validar_documento(cls, v: str, info) -> str:
        """Valida formato de documento según tipo"""
        tipo = info.data.get("tipo_documento")
        if tipo in [TipoDocumento.CC, TipoDocumento.CE, TipoDocumento.TI]:
            if not v.isdigit():
                raise ValueError(f"El documento tipo {tipo} debe contener solo dígitos")
        return v
    
    @field_validator("fecha_retiro")
    @classmethod
    def validar_fecha_retiro(cls, v: Optional[date], info) -> Optional[date]:
        """Valida que fecha de retiro sea posterior a fecha de ingreso"""
        if v is not None:
            fecha_ingreso = info.data.get("fecha_ingreso")
            if fecha_ingreso and v < fecha_ingreso:
                raise ValueError("La fecha de retiro no puede ser anterior a la fecha de ingreso")
        return v
    
    @field_validator("salario_basico")
    @classmethod
    def validar_salario_minimo(cls, v: Decimal) -> Decimal:
        """Valida que el salario sea al menos el mínimo legal (2024: $1,300,000)"""
        SALARIO_MINIMO_2024 = Decimal("1300000")
        if v < SALARIO_MINIMO_2024:
            raise ValueError(f"El salario no puede ser inferior al mínimo legal: ${SALARIO_MINIMO_2024:,.0f}")
        return v
    
    @computed_field
    @property
    def nombre_completo(self) -> str:
        """Retorna el nombre completo del empleado"""
        nombres = [
            self.primer_nombre,
            self.segundo_nombre if self.segundo_nombre else "",
            self.primer_apellido,
            self.segundo_apellido if self.segundo_apellido else ""
        ]
        return " ".join([n for n in nombres if n]).strip()
    
    @computed_field
    @property
    def ibc_salud(self) -> Decimal:
        """Ingreso Base de Cotización para salud (al menos 1 SMMLV)"""
        SALARIO_MINIMO_2024 = Decimal("1300000")
        return max(self.salario_basico, SALARIO_MINIMO_2024)
    
    @computed_field
    @property
    def ibc_pension(self) -> Decimal:
        """Ingreso Base de Cotización para pensión"""
        # Para salario integral, el 70% es el IBC
        if self.es_salario_integral:
            return self.salario_basico * Decimal("0.70")
        return self.salario_basico


class Novedad(BaseModel):
    """Modelo para novedades que afectan el cálculo de nómina"""
    
    model_config = ConfigDict(validate_assignment=True)
    
    tipo: TipoNovedad
    fecha_inicio: date
    fecha_fin: date
    dias: int = Field(..., ge=1, description="Cantidad de días de la novedad")
    valor: Optional[Decimal] = Field(
        default=None,
        ge=0,
        description="Valor asociado a la novedad si aplica"
    )
    numero_radicado: Optional[str] = Field(
        default=None,
        description="Número de radicado de incapacidad o licencia ante EPS"
    )
    observaciones: Optional[str] = Field(default=None, max_length=500)
    
    @field_validator("fecha_fin")
    @classmethod
    def validar_fechas(cls, v: date, info) -> date:
        """Valida que fecha fin sea posterior o igual a fecha inicio"""
        fecha_inicio = info.data.get("fecha_inicio")
        if fecha_inicio and v < fecha_inicio:
            raise ValueError("La fecha fin no puede ser anterior a la fecha inicio")
        return v


class HoraExtra(BaseModel):
    """Modelo para registro de horas extras trabajadas"""
    
    model_config = ConfigDict(validate_assignment=True)
    
    tipo: TipoHoraExtra
    cantidad: Decimal = Field(..., gt=0, description="Cantidad de horas trabajadas")
    fecha: date = Field(..., description="Fecha en que se trabajaron")
    
    @field_validator("cantidad")
    @classmethod
    def validar_cantidad_razonable(cls, v: Decimal) -> Decimal:
        """Valida que la cantidad de horas sea razonable (máximo 2 horas diarias según CST)"""
        if v > Decimal("4"):  # Máximo 4 horas extra por día en casos especiales
            raise ValueError("La cantidad de horas extras diarias no puede exceder 4 horas")
        return v


class ConceptoDevengado(BaseModel):
    """Concepto individual de devengado en nómina"""
    
    model_config = ConfigDict(validate_assignment=True)
    
    codigo: str = Field(..., description="Código interno del concepto")
    descripcion: str = Field(..., min_length=1, max_length=255)
    valor: Decimal = Field(..., ge=0)
    es_base_prestacional: bool = Field(
        default=True,
        description="Si el concepto hace parte de la base para prestaciones sociales"
    )
    es_base_aportes: bool = Field(
        default=True,
        description="Si el concepto hace parte del IBC para aportes PILA"
    )
    es_base_retencion: bool = Field(
        default=True,
        description="Si el concepto hace parte de la base para retención en la fuente"
    )


class Devengados(BaseModel):
    """Estructura completa de devengados de un periodo"""
    
    model_config = ConfigDict(validate_assignment=True)
    
    salario_basico: Decimal = Field(..., ge=0)
    auxilio_transporte: Decimal = Field(default=Decimal("0"), ge=0)
    horas_extras: List[HoraExtra] = Field(default_factory=list)
    recargos_nocturnos: Decimal = Field(default=Decimal("0"), ge=0)
    trabajo_dominical: Decimal = Field(default=Decimal("0"), ge=0)
    
    # Prestaciones sociales
    cesantias: Decimal = Field(default=Decimal("0"), ge=0)
    prima_servicios: Decimal = Field(default=Decimal("0"), ge=0)
    vacaciones: Decimal = Field(default=Decimal("0"), ge=0)
    intereses_cesantias: Decimal = Field(default=Decimal("0"), ge=0)
    
    # Otros conceptos
    bonificaciones: Decimal = Field(default=Decimal("0"), ge=0)
    comisiones: Decimal = Field(default=Decimal("0"), ge=0)
    viáticos: Decimal = Field(default=Decimal("0"), ge=0)
    
    # Compensaciones no salariales
    compensaciones: List[ConceptoDevengado] = Field(default_factory=list)
    
    # Otros devengados personalizados
    otros: List[ConceptoDevengado] = Field(default_factory=list)
    
    @computed_field
    @property
    def total_horas_extras(self) -> Decimal:
        """Calcula el total de todas las horas extras"""
        # Nota: El valor debe ser calculado previamente según las tarifas
        # Este es solo un acumulado
        return sum((he.cantidad for he in self.horas_extras), Decimal("0"))
    
    @computed_field
    @property
    def total_devengado(self) -> Decimal:
        """Calcula el total de devengados"""
        total = (
            self.salario_basico +
            self.auxilio_transporte +
            self.recargos_nocturnos +
            self.trabajo_dominical +
            self.cesantias +
            self.prima_servicios +
            self.vacaciones +
            self.intereses_cesantias +
            self.bonificaciones +
            self.comisiones +
            self.viáticos
        )
        
        # Sumar compensaciones y otros
        total += sum((c.valor for c in self.compensaciones), Decimal("0"))
        total += sum((o.valor for o in self.otros), Decimal("0"))
        
        return total


class ConceptoDeduccion(BaseModel):
    """Concepto individual de deducción en nómina"""
    
    model_config = ConfigDict(validate_assignment=True)
    
    codigo: str = Field(..., description="Código interno del concepto")
    descripcion: str = Field(..., min_length=1, max_length=255)
    valor: Decimal = Field(..., ge=0)


class Deducciones(BaseModel):
    """Estructura completa de deducciones de un periodo"""
    
    model_config = ConfigDict(validate_assignment=True)
    
    # Seguridad social (aporte empleado)
    salud: Decimal = Field(default=Decimal("0"), ge=0, description="4% sobre IBC")
    pension: Decimal = Field(default=Decimal("0"), ge=0, description="4% sobre IBC")
    fondo_solidaridad_pensional: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description="1% o 2% según salario (>= 4 SMMLV)"
    )
    
    # Retención en la fuente
    retencion_fuente: Decimal = Field(default=Decimal("0"), ge=0)
    
    # Otras deducciones legales
    libranzas: Decimal = Field(default=Decimal("0"), ge=0)
    embargos_judiciales: Decimal = Field(default=Decimal("0"), ge=0)
    cuotas_sindicales: Decimal = Field(default=Decimal("0"), ge=0)
    
    # Deducciones voluntarias
    aportes_voluntarios_pension: Decimal = Field(default=Decimal("0"), ge=0)
    aportes_voluntarios_afc: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description="Ahorro para el fomento de la construcción"
    )
    
    # Descuentos varios
    descuentos_cooperativa: Decimal = Field(default=Decimal("0"), ge=0)
    descuentos_empresa: Decimal = Field(default=Decimal("0"), ge=0)
    
    # Otras deducciones personalizadas
    otras: List[ConceptoDeduccion] = Field(default_factory=list)
    
    @computed_field
    @property
    def total_deduccion(self) -> Decimal:
        """Calcula el total de deducciones"""
        total = (
            self.salud +
            self.pension +
            self.fondo_solidaridad_pensional +
            self.retencion_fuente +
            self.libranzas +
            self.embargos_judiciales +
            self.cuotas_sindicales +
            self.aportes_voluntarios_pension +
            self.aportes_voluntarios_afc +
            self.descuentos_cooperativa +
            self.descuentos_empresa
        )
        
        # Sumar otras deducciones
        total += sum((d.valor for d in self.otras), Decimal("0"))
        
        return total


class NominaEmpleado(BaseModel):
    """Modelo completo de nómina para un empleado en un periodo"""
    
    model_config = ConfigDict(validate_assignment=True)
    
    empleado: Empleado
    periodo_inicio: date
    periodo_fin: date
    tipo_periodo: TipoPeriodo
    dias_trabajados: int = Field(..., ge=0, le=31, description="Días trabajados en el periodo")
    
    # Novedades del periodo
    novedades: List[Novedad] = Field(default_factory=list)
    
    # Devengados y deducciones
    devengados: Devengados
    deducciones: Deducciones
    
    # Información de pago
    fecha_pago: date
    metodo_pago: str = Field(default="transferencia", pattern="^(transferencia|efectivo|cheque)$")
    
    # Notas adicionales
    notas: Optional[str] = Field(default=None, max_length=1000)
    
    @field_validator("periodo_fin")
    @classmethod
    def validar_periodo(cls, v: date, info) -> date:
        """Valida que el periodo fin sea posterior a periodo inicio"""
        periodo_inicio = info.data.get("periodo_inicio")
        if periodo_inicio and v < periodo_inicio:
            raise ValueError("El periodo fin no puede ser anterior al periodo inicio")
        return v
    
    @field_validator("fecha_pago")
    @classmethod
    def validar_fecha_pago(cls, v: date, info) -> date:
        """Valida que la fecha de pago no sea anterior al periodo"""
        periodo_fin = info.data.get("periodo_fin")
        if periodo_fin and v < periodo_fin:
            raise ValueError("La fecha de pago no puede ser anterior al fin del periodo")
        return v
    
    @computed_field
    @property
    def neto_pagar(self) -> Decimal:
        """Calcula el valor neto a pagar al empleado"""
        return self.devengados.total_devengado - self.deducciones.total_deduccion
    
    @computed_field
    @property
    def dias_periodo(self) -> int:
        """Calcula los días totales del periodo"""
        return (self.periodo_fin - self.periodo_inicio).days + 1


class LiquidacionFinal(BaseModel):
    """Modelo para liquidación final de contrato"""
    
    model_config = ConfigDict(validate_assignment=True)
    
    empleado: Empleado
    fecha_retiro: date
    motivo_retiro: str = Field(..., min_length=1, max_length=500)
    
    # Prestaciones sociales acumuladas
    cesantias_acumuladas: Decimal = Field(..., ge=0)
    intereses_cesantias: Decimal = Field(..., ge=0)
    prima_servicios: Decimal = Field(..., ge=0)
    vacaciones_compensadas: Decimal = Field(..., ge=0)
    
    # Salarios pendientes
    salarios_pendientes: Decimal = Field(default=Decimal("0"), ge=0)
    
    # Indemnizaciones
    indemnizacion_despido: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description="Indemnización por despido sin justa causa si aplica"
    )
    
    # Otras acreencias
    bonificaciones_pendientes: Decimal = Field(default=Decimal("0"), ge=0)
    
    # Deducciones finales
    deducciones_finales: Deducciones
    
    # Fecha de pago de liquidación
    fecha_pago: date
    
    @field_validator("fecha_retiro")
    @classmethod
    def validar_retiro(cls, v: date, info) -> date:
        """Valida que la fecha de retiro sea posterior al ingreso"""
        empleado = info.data.get("empleado")
        if empleado and v < empleado.fecha_ingreso:
            raise ValueError("La fecha de retiro no puede ser anterior a la fecha de ingreso")
        return v
    
    @computed_field
    @property
    def total_prestaciones(self) -> Decimal:
        """Total de prestaciones sociales"""
        return (
            self.cesantias_acumuladas +
            self.intereses_cesantias +
            self.prima_servicios +
            self.vacaciones_compensadas
        )
    
    @computed_field
    @property
    def total_liquidacion(self) -> Decimal:
        """Total bruto de la liquidación"""
        return (
            self.total_prestaciones +
            self.salarios_pendientes +
            self.indemnizacion_despido +
            self.bonificaciones_pendientes
        )
    
    @computed_field
    @property
    def neto_liquidacion(self) -> Decimal:
        """Valor neto a pagar en liquidación"""
        return self.total_liquidacion - self.deducciones_finales.total_deduccion


class DocumentoNominaElectronica(BaseModel):
    """Modelo para documento de nómina electrónica DIAN"""
    
    model_config = ConfigDict(validate_assignment=True)
    
    # Información del documento
    numero_documento: str = Field(..., description="Número consecutivo del documento")
    prefijo: Optional[str] = Field(default=None)
    fecha_emision: datetime = Field(default_factory=datetime.now)
    
    # Información de la empresa
    empresa: ConfiguracionEmpresa
    
    # Nómina del empleado
    nomina: NominaEmpleado
    
    # Software y ambiente
    ambiente: str = Field(default="produccion", pattern="^(produccion|habilitacion)$")
    software_id: str = Field(..., description="ID del software registrado ante DIAN")
    software_pin: str = Field(..., description="PIN de seguridad del software")
    
    # CUNE (Código Único de Nómina Electrónica)
    cune: Optional[str] = Field(
        default=None,
        description="Código único generado por DIAN tras validación"
    )
    
    @field_validator("numero_documento")
    @classmethod
    def validar_consecutivo(cls, v: str) -> str:
        """Valida formato del número de documento"""
        if not v:
            raise ValueError("El número de documento es obligatorio")
        return v
    
    def generar_xml(self) -> str:
        """
        Genera el XML del documento de nómina electrónica
        Debe ser implementado por el módulo xml_dian
        """
        from nomina_co.xml_dian import generar_xml_nomina
        return generar_xml_nomina(self)