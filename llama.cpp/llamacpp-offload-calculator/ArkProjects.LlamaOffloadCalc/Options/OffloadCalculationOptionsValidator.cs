using FluentValidation;

namespace ArkProjects.LlmCalc.Options;

public class OffloadCalculationOptionsValidator : AbstractValidator<OffloadCalculationOptions>
{
    public OffloadCalculationOptionsValidator()
    {
        RuleFor(x => x.GgufFile)
            .NotEmpty()
            .Must(x => File.Exists(x)).WithMessage("gguf file not exist");

        RuleFor(x => x.Devices)
            .Must(x => x.GroupBy(y => y.Value.Id).All(y => y.Count() == 1))
            .WithMessage("Each device must have unique id");
        RuleFor(x => x.OffloadRules)
            .Must(x => x.GroupBy(y => y.Value.Id).All(y => y.Count() == 1))
            .WithMessage("Each offload rule must have unique id");

        RuleFor(x => x.Devices)
            .Must(x => x.Count(d => d.Value.Type == LLamaDeviceType.Unknown) == 0)
            .WithMessage("Type must be set for each device");
        RuleFor(x => x.Devices)
            .Must(x => x.Count(d => d.Value.Type == LLamaDeviceType.GPU) >= 1)
            .WithMessage("1 or more GPUs must be defined");
        RuleFor(x => x.Devices)
            .Must(x => x.Count(d => d.Value.Type == LLamaDeviceType.CPU) == 1)
            .WithMessage("Single gpu must be defined");
        RuleFor(x => x.OffloadRules)
            .Must(x => x.Count > 0)
            .WithMessage("1 or more offloading rule must be defined");
    }
}
