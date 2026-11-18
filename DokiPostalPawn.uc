//=============================================================================
// DokiPostalPawn.uc
// Doki Doki Postal Club — Secondary Jiggle Physics, Head Cleanup, Doki Selector,
// and Split-Screen Co-op Viewport (Unreal Engine 2 / Postal 2).
//=============================================================================
class DokiPostalPawn extends PersonPawn;

var vector PrevVelocity;
var rotator JiggleDispL, JiggleDispR;
var rotator JiggleVelL, JiggleVelR;
var float JiggleStiffness;
var float JiggleDamping;

simulated function Tick(float DeltaTime)
{
    local float Speed, OscL, OscR;
    local rotator TargetRotL, TargetRotR;

    Super.Tick(DeltaTime);

    // Ensure no random NPC Head actor remains attached on full-body Doki meshes
    if (!bHasHead && myHead != None)
    {
        DestroyHeadBoltons();
        DestroyBoltons();
        myHead.Destroy();
        myHead = None;
    }

    // Spring-damper secondary inertia on jiggle_L and jiggle_R parented to MALE01 spine2
    Speed = VSize(Velocity);
    OscL = Sin(Level.TimeSeconds * 14.0) * Speed * 1.4 + Velocity.Z * 1.8;
    OscR = Sin(Level.TimeSeconds * 14.0 + 0.35) * Speed * 1.4 + Velocity.Z * 1.8;

    TargetRotL = rot(1, 0, 0) * OscL;
    TargetRotR = rot(1, 0, 0) * OscR;

    JiggleVelL += (TargetRotL - JiggleDispL) * (JiggleStiffness * DeltaTime);
    JiggleVelL *= FMax(0.0, 1.0 - JiggleDamping * DeltaTime);
    JiggleDispL += JiggleVelL * DeltaTime;

    JiggleVelR += (TargetRotR - JiggleDispR) * (JiggleStiffness * DeltaTime);
    JiggleVelR *= FMax(0.0, 1.0 - JiggleDamping * DeltaTime);
    JiggleDispR += JiggleVelR * DeltaTime;

    SetBoneRotation('jiggle_L', JiggleDispL, 0, 1.0);
    SetBoneRotation('jiggle_R', JiggleDispR, 0, 1.0);
}

defaultproperties
{
    bHasHead=False
    bHeadCanComeOff=False
    bChameleon=False
    bNoChamelBoltons=True
    HeadClass=None
    JiggleStiffness=140.0
    JiggleDamping=9.5
}

